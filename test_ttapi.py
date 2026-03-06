"""TTAPI Upload API 테스트 스크립트"""
import requests
import sys

# TTAPI KEY 
api_key = "58618a8a-c885-7248-3ad7-fd8c774d65ae"
file_path = "test.mp3"

def test_upload(api_key: str, file_path: str):
    url = "https://api.ttapi.io/suno/v1/upload"
    headers = {"TT-API-KEY": api_key}
    
    print(f"📤 파일 업로드 테스트: {file_path}")
    print(f"🔗 URL: {url}")
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.split("/")[-1], f, "audio/mpeg")}
            resp = requests.post(url, headers=headers, files=files, timeout=60)
        
        print(f"📊 HTTP Status: {resp.status_code}")
        print(f"📋 Response Headers:")
        for k, v in resp.headers.items():
            if k.lower() in ['content-type', 'x-request-id', 'date']:
                print(f"   {k}: {v}")
        
        print(f"\n📄 Response Body:")
        try:
            print(resp.json())
        except:
            print(resp.text[:500])
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_ttapi.py <API_KEY> <AUDIO_FILE>")
        sys.exit(1)
    test_upload(sys.argv[1], sys.argv[2])
