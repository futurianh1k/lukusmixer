__version__ = "0.1"


from transformers import AutoConfig, AutoModel

from .configuration_songgen import SongGenConfig, SongGenDecoderConfig
from .xcodec_wrapper import XCodecConfig, XCodecModel
from .modeling_songgen_mixed import (
    SongGenForCausalLM,
    SongGenMixedForConditionalGeneration,
    apply_delay_pattern_mask,
    build_delay_pattern_mask,
)

from .modeling_songgen_dual_track import (
    SongGenDualTrackForConditionalGeneration,
    split_combined_track_input_ids,
    build_combined_delay_pattern_mask,
    combine_track_input_ids
)

from .processing_songgen import SongGenProcessor

# from .streamer import SongGenStreamer

from .lyrics_utils.lyrics_tokenizer import VoiceBpeTokenizer

AutoConfig.register("xcodec", XCodecConfig)
AutoModel.register(XCodecConfig, XCodecModel)


