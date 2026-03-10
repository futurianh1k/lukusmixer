"""
Banquet Service - 쿼리 기반 음원 분리 래퍼
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
query-bandit (Banquet) 모델을 래핑하여
레퍼런스 쿼리 오디오 기반의 악기 분리를 수행한다.

참고 출처:
  - Banquet: https://github.com/kwatcharasupat/query-bandit (MIT)
  - PaSST: https://github.com/kkoutini/PaSST (Apache-2.0)
  - Watcharasupat & Lerch, "A Stem-Agnostic Single-Decoder System
    for Music Source Separation Beyond Four Stems", ISMIR 2024

사용법:
  service = BanquetService()
  result = service.separate("other.wav", {"strings": "violin_query.wav"}, "/output")
"""

import logging
import os
import sys
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("lukus.banquet")

BANQUET_DIR = Path(__file__).parent / "query_bandit"
BANQUET_CONFIG_ROOT = BANQUET_DIR / "config"
BANQUET_EXPT_CONFIG = BANQUET_DIR / "expt" / "bandit-everything-test.yml"
BANQUET_CHECKPOINT_DIR = BANQUET_DIR / "checkpoints"
DEFAULT_CHECKPOINT = "ev-pre-aug.ckpt"

QUERY_AUDIO_DIR = Path(__file__).parent / "banquet_queries"

BANQUET_STEMS = {
    "strings": {
        "ko": "현악기",
        "en": "Strings",
        "query_file": "strings_query.wav",
        "color": "#a78bfa",
    },
    "brass": {
        "ko": "금관악기",
        "en": "Brass",
        "query_file": "brass_query.wav",
        "color": "#fbbf24",
    },
    "woodwinds": {
        "ko": "목관악기",
        "en": "Woodwinds",
        "query_file": "woodwinds_query.wav",
        "color": "#34d399",
    },
    "synthesizer": {
        "ko": "신디사이저",
        "en": "Synthesizer",
        "query_file": "synthesizer_query.wav",
        "color": "#f472b6",
    },
}

BANQUET_BATCH_SIZE = int(os.environ.get("BANQUET_BATCH_SIZE", 3))
MODEL_FS = 44100
QUERY_LENGTH_SEC = 10.0


class BanquetService:
    """Banquet 모델 래핑 — 싱글톤 형태로 모델을 한 번만 로드"""

    def __init__(self, checkpoint: Optional[str] = None):
        self._system = None
        self._loaded = False
        self._available = False
        self._batch_size = BANQUET_BATCH_SIZE

        self._ckpt_path = checkpoint or str(
            BANQUET_CHECKPOINT_DIR / DEFAULT_CHECKPOINT
        )

        self._check_availability()

    def _check_availability(self):
        """Banquet 모델 사용 가능 여부 확인"""
        if not Path(self._ckpt_path).exists():
            logger.warning(
                "Banquet 체크포인트 없음: %s "
                "(Zenodo에서 다운로드 필요: https://zenodo.org/records/13694558)",
                self._ckpt_path,
            )
            return

        try:
            import torch          # noqa: F401
            import torchaudio     # noqa: F401

            if not BANQUET_EXPT_CONFIG.exists():
                logger.warning("Banquet 설정 파일 없음: %s", BANQUET_EXPT_CONFIG)
                return

            self._available = True
            logger.info("Banquet 사용 가능 (checkpoint=%s)", self._ckpt_path)
        except ImportError as e:
            logger.warning("Banquet 종속성 누락: %s", e)

    @property
    def available(self) -> bool:
        return self._available

    def _ensure_loaded(self):
        """모델 지연 로딩 — 첫 호출 시에만 실행"""
        if self._loaded:
            return

        if not self._available:
            raise RuntimeError("Banquet 모델이 사용 불가능합니다")

        os.environ.setdefault("CONFIG_ROOT", str(BANQUET_CONFIG_ROOT))

        original_path = list(sys.path)
        sys.path.insert(0, str(BANQUET_DIR))

        try:
            import torch
            import torchaudio  # noqa: F401
            from omegaconf import OmegaConf

            config_path = str(BANQUET_EXPT_CONFIG)
            config = OmegaConf.load(config_path)
            config_dict = {}
            for k, v in config.items():
                if isinstance(v, str) and v.endswith(".yml"):
                    config_dict[k] = OmegaConf.load(v)
                else:
                    config_dict[k] = v
            config = OmegaConf.merge(config_dict)

            config.data.inference_kwargs.batch_size = self._batch_size

            from core.models.e2e.bandit.bandit import PasstFiLMConditionedBandit
            from core.losses.l1snr import L1SNRLoss
            from core.losses.base import BaseLossHandler
            from core.metrics.base import BaseMetricHandler, MultiModeMetricHandler
            from core.metrics.snr import (
                SafeScaleInvariantSignalNoiseRatio,
                SafeSignalNoiseRatio,
                PredictedDecibels,
                TargetDecibels,
            )
            from core.models.ebase import EndToEndLightningSystem
            import torchmetrics as tm
            from torch import nn
            from types import SimpleNamespace

            model_config = config.model
            model = PasstFiLMConditionedBandit(**model_config.get("kwargs", {}))

            loss_config = config.loss
            loss_cls_name = loss_config.cls
            loss_kwargs = loss_config.get("kwargs", {})
            inner_loss = L1SNRLoss(**loss_kwargs)
            loss_handler = BaseLossHandler(
                loss=inner_loss,
                modality=loss_config.modality,
                name=loss_config.get("name", None),
            )

            dummy_stems = config.stems
            dummy_metric_dict = {
                stem: BaseMetricHandler(
                    stem=stem,
                    metric=tm.MetricCollection(
                        SafeSignalNoiseRatio(),
                        SafeScaleInvariantSignalNoiseRatio(),
                        PredictedDecibels(),
                        TargetDecibels(),
                    ),
                    modality="audio",
                    name="snr",
                )
                for stem in dummy_stems
            }
            metrics = MultiModeMetricHandler(
                train_metrics=dummy_metric_dict,
                val_metrics=dummy_metric_dict,
                test_metrics=dummy_metric_dict,
            )

            optim_config = config.optim
            optim_bundle = SimpleNamespace(
                optimizer=SimpleNamespace(
                    cls=getattr(torch.optim, optim_config.optimizer.cls),
                    kwargs=optim_config.optimizer.get("kwargs", {}),
                ),
                scheduler=None,
            )

            self._system = EndToEndLightningSystem.load_from_checkpoint(
                os.path.expandvars(self._ckpt_path),
                strict=True,
                model=model,
                loss_handler=loss_handler,
                metrics=metrics,
                augmentation_handler=nn.Identity(),
                inference_handler=config.data.inference_kwargs,
                optimization_bundle=optim_bundle,
                fast_run=config.fast_run,
                batch_size=config.data.batch_size,
                effective_batch_size=config.data.get("effective_batch_size", None),
                commitment_weight=config.get("commitment_weight", 1.0),
            )

            if torch.cuda.is_available():
                self._system.cuda()
            self._system.eval()

            self._loaded = True
            logger.info("Banquet 모델 로드 완료 (batch_size=%d)", self._batch_size)

        except Exception as e:
            logger.error("Banquet 모델 로드 실패: %s", e)
            self._available = False
            raise
        finally:
            sys.path = original_path

    def separate_one(
        self,
        input_path: str,
        query_path: str,
        output_path: str,
        stem_name: str = "target",
    ) -> str:
        """단일 쿼리로 악기 분리 실행

        Args:
            input_path: 입력 오디오 파일 경로
            query_path: 쿼리(레퍼런스) 오디오 파일 경로
            output_path: 출력 WAV 파일 경로
            stem_name: 스템 식별자

        Returns:
            output_path
        """
        self._ensure_loaded()

        import torch
        import torchaudio as ta

        mixture, fsm = ta.load(input_path)
        query, fsq = ta.load(query_path)

        if fsm != MODEL_FS:
            mixture = ta.functional.resample(mixture, orig_freq=fsm, new_freq=MODEL_FS)
        if fsq != MODEL_FS:
            query = ta.functional.resample(query, orig_freq=fsq, new_freq=MODEL_FS)

        target_len = int(QUERY_LENGTH_SEC * MODEL_FS)
        if query.shape[1] > target_len:
            query = query[:, :target_len]
        elif query.shape[1] < target_len:
            repeats = target_len // query.shape[1] + 1
            query = torch.cat([query] * repeats, dim=1)[:, :target_len]

        device = self._system.device
        query = query.unsqueeze(0).to(device=device)
        mixture_t = mixture.unsqueeze(0).to(device=device)

        batch = {
            "mixture": {"audio": mixture_t},
            "query": {"audio": query},
            "metadata": {"stem": [stem_name]},
            "estimates": {},
        }

        with torch.no_grad():
            out = self._system.chunked_inference(batch)

        estimate = out["estimates"][stem_name]["audio"].squeeze().cpu()

        if fsm != MODEL_FS:
            estimate = ta.functional.resample(
                estimate, orig_freq=MODEL_FS, new_freq=fsm
            )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        ta.save(output_path, estimate, fsm)
        logger.info("Banquet 분리 완료: %s → %s", stem_name, output_path)
        return output_path

    def separate_multi(
        self,
        input_path: str,
        query_map: Dict[str, str],
        output_dir: str,
        progress_cb: Optional[Callable] = None,
    ) -> Dict[str, str]:
        """여러 쿼리를 순차적으로 실행하여 다중 악기 분리

        Args:
            input_path: 입력 오디오 (예: "other" 스템)
            query_map: {stem_name: query_audio_path, ...}
            output_dir: 출력 디렉토리
            progress_cb: 진행상황 콜백

        Returns:
            {stem_name: output_file_path, ...}
        """
        results: Dict[str, str] = {}
        total = len(query_map)

        for i, (stem_name, query_path) in enumerate(query_map.items(), 1):
            if progress_cb:
                progress_cb(
                    f"Banquet 분리 ({i}/{total}): "
                    f"{BANQUET_STEMS.get(stem_name, {}).get('ko', stem_name)}..."
                )

            output_path = os.path.join(output_dir, f"{stem_name}.wav")
            try:
                self.separate_one(input_path, query_path, output_path, stem_name)
                results[stem_name] = output_path
            except Exception as e:
                logger.error("Banquet %s 분리 실패: %s", stem_name, e)

        return results

    def get_default_queries(self) -> Dict[str, str]:
        """기본 레퍼런스 쿼리 오디오 경로 반환"""
        queries = {}
        for stem_name, info in BANQUET_STEMS.items():
            qpath = QUERY_AUDIO_DIR / info["query_file"]
            if qpath.exists():
                queries[stem_name] = str(qpath)
            else:
                logger.warning("쿼리 파일 없음: %s", qpath)
        return queries
