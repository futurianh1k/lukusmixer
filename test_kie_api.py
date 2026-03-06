#!/usr/bin/env python3
"""
KIE.AI Suno API 테스트 스크립트
- kie.ai는 URL 기반 업로드를 사용합니다
- 파일을 먼저 클라우드에 업로드하고 URL을 제공해야 합니다

사용법:
    python test_kie_api.py <KIE_API_KEY> <AUDIO_URL>
    
예시:
    python test_kie_api.py "your-api-key" "https://example.com/audio.mp3"
"""

import requests
import sys
import time
import json


def test_upload_cover(api_key: str, audio_url: str):
    """kie.ai Upload & Cover API 테스트"""
    
    url = "https://api.kie.ai/api/v1/generate/upload-cover"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "uploadUrl": audio_url,
        "customMode": False,
        "instrumental": False,
        "prompt": "Create a remix version",
        "model": "V4"
    }
    
    print(f"🎵 KIE.AI Upload & Cover 테스트")
    print(f"🔗 URL: {url}")
    print(f"📎 Audio URL: {audio_url}")
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        print(f"📊 HTTP Status: {resp.status_code}")
        print(f"📄 Response:")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        
        if resp.status_code == 200:
            data = resp.json()
            task_id = data.get("data", {}).get("taskId")
            if task_id:
                print(f"\n✅ 작업 ID: {task_id}")
                print("결과 확인: GET https://api.kie.ai/api/v1/generate/record-info?taskId=" + task_id)
                
    except Exception as e:
        print(f"❌ Error: {e}")


def test_text_generate(api_key: str):
    """kie.ai 텍스트 기반 음악 생성 테스트"""
    
    url = "https://api.kie.ai/api/v1/generate/music"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "prompt": "A cheerful pop song about summer",
        "customMode": False,
        "instrumental": True,
        "model": "V4"
    }
    
    print(f"\n🎵 KIE.AI 텍스트 기반 생성 테스트")
    print(f"🔗 URL: {url}")
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        print(f"📊 HTTP Status: {resp.status_code}")
        print(f"📄 Response:")
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n사용법:")
        print("  python test_kie_api.py <KIE_API_KEY>                    # 텍스트 생성 테스트")
        print("  python test_kie_api.py <KIE_API_KEY> <AUDIO_URL>        # 커버 생성 테스트")
        sys.exit(1)
    
    api_key = sys.argv[1]
    
    if len(sys.argv) >= 3:
        audio_url = sys.argv[2]
        test_upload_cover(api_key, audio_url)
    else:
        test_text_generate(api_key)
