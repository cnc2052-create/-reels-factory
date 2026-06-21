"""
setup.py — 최초 1회 실행: 가상환경 생성 + 패키지 설치 + ffmpeg 확인
"""
import subprocess
import sys
import shutil
from pathlib import Path

BASE = Path(__file__).parent
VENV = BASE / "venv"


def run(cmd: list, **kw):
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, **kw)
    if result.returncode != 0:
        print(f"  [실패] 종료 코드: {result.returncode}")
        return False
    return True


def main():
    print("=" * 50)
    print("[1/3] Python 가상환경 생성")
    print("=" * 50)
    if VENV.exists():
        print(f"  이미 존재: {VENV}")
    else:
        run([sys.executable, "-m", "venv", str(VENV)])
        print(f"  생성 완료: {VENV}")

    # 가상환경 내 pip 경로
    if sys.platform == "win32":
        pip = VENV / "Scripts" / "pip.exe"
        python = VENV / "Scripts" / "python.exe"
    else:
        pip = VENV / "bin" / "pip"
        python = VENV / "bin" / "python"

    print("\n[2/3] 패키지 설치 (requirements.txt)")
    run([str(pip), "install", "--upgrade", "pip"], capture_output=True)
    run([str(pip), "install", "-r", str(BASE / "requirements.txt")])

    print("\n[3/3] FFmpeg 확인")
    if shutil.which("ffmpeg"):
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        ver_line = result.stdout.splitlines()[0] if result.stdout else "버전 확인 불가"
        print(f"  ✓ FFmpeg 설치 확인: {ver_line}")
    else:
        print("  ✗ FFmpeg를 찾을 수 없습니다.")
        print()
        print("  ▶ Windows 설치 방법 (권장순):")
        print()
        print("  방법 A — winget (가장 간단, Windows 10 이상)")
        print("    관리자 PowerShell에서 실행:")
        print("    winget install ffmpeg")
        print()
        print("  방법 B — Chocolatey")
        print("    1. https://chocolatey.org/install 에서 Chocolatey 설치")
        print("    2. 관리자 PowerShell: choco install ffmpeg")
        print()
        print("  방법 C — 수동 설치")
        print("    1. https://www.gyan.dev/ffmpeg/builds/ → ffmpeg-release-essentials.zip 다운로드")
        print("    2. C:\\ffmpeg\\ 에 압축 해제")
        print("    3. 시스템 환경변수 PATH에 C:\\ffmpeg\\bin 추가")
        print("    4. 새 터미널에서 ffmpeg -version 으로 확인")
        print()
        print("  ※ FFmpeg 설치 후 setup.py를 재실행하세요.")
        return

    print()
    print("=" * 50)
    print("설치 완료! 이제 아래 순서로 진행하세요:")
    print()
    print("  1. .env.example → .env 로 복사 후 API 키 입력")
    print("  2. assets/ 폴더에 background.jpg / font.ttf / bgm.mp3 배치")
    if sys.platform == "win32":
        print(f"  3. venv\\Scripts\\activate")
    else:
        print(f"  3. source venv/bin/activate")
    print("  4. python main.py")
    print("=" * 50)


if __name__ == "__main__":
    main()
