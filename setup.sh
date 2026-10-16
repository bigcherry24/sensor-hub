#!/bin/bash
set -e

echo "================================================"
echo "🔧 sensor-hub 개발 환경 설정"
echo "================================================"
echo ""

# Python 버전 확인
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "📌 Python 버전: $python_version"
echo ""

# 플랫폼 감지
if grep -q "Raspberry Pi" /sys/firmware/devicetree/base/model 2>/dev/null; then
    PLATFORM="raspberry"
    echo "🎯 플랫폼: Raspberry Pi 감지"
else
    PLATFORM="other"
    echo "🎯 플랫폼: 일반 Linux/Mac"
fi
echo ""

# rpi 환경 (라즈베리파이에서만)
if [ "$PLATFORM" = "raspberry" ]; then
    echo "📱 [1/2] rpi 환경 설정 중..."
    cd rpi
    if [ -d "venv" ]; then
        echo "  ⚠️  venv 이미 존재합니다. 제거 후 재생성..."
        rm -rf venv
    fi
    python3 -m venv venv
    echo "  ✅ venv 생성 완료"

    echo "  📦 의존성 설치 중..."
    source venv/bin/activate
    pip install --upgrade pip setuptools wheel > /dev/null 2>&1
    pip install -r requirements.txt > /dev/null 2>&1
    deactivate
    echo "  ✅ rpi 환경 설정 완료"
    cd ..
    echo ""
else
    echo "⏭️  [1/2] rpi 환경 설정 스킵"
    echo "  (라즈베리파이에서만 설정 필요)"
    echo ""
    echo "  📍 라즈베리파이에서 실행:"
    echo "     cd rpi"
    echo "     python3 -m venv venv"
    echo "     source venv/bin/activate"
    echo "     pip install -r requirements.txt"
    echo ""
fi

# 서버 환경 (모든 플랫폼)
echo "🖥️  [2/2] server 환경 설정 중..."
cd server
if [ -d "venv" ]; then
    echo "  ⚠️  venv 이미 존재합니다. 제거 후 재생성..."
    rm -rf venv
fi
python3 -m venv venv
echo "  ✅ venv 생성 완료"

echo "  📦 의존성 설치 중..."
source venv/bin/activate
pip install --upgrade pip setuptools wheel > /dev/null 2>&1
pip install -r requirements.txt > /dev/null 2>&1
deactivate
echo "  ✅ server 환경 설정 완료"
cd ..
echo ""

echo "================================================"
echo "✅ 개발 환경 설정 완료!"
echo "================================================"
echo ""
echo "📖 사용법:"
echo ""
echo "  📱 라즈베리파이 퍼블리셔 실행:"
echo "     cd rpi"
echo "     source venv/bin/activate"
echo "     python3 publisher.py"
echo ""
echo "  🖥️  서버 수집기 실행:"
echo "     cd server"
echo "     source venv/bin/activate"
echo "     cd collector"
echo "     python3 collector.py"
echo ""
echo "  📂 프로젝트 구조:"
echo "     sensor-hub/"
echo "     ├── rpi/"
echo "     │   ├── venv/              (Python 환경)"
echo "     │   ├── sensors/"
echo "     │   ├── publisher.py"
echo "     │   └── requirements.txt"
echo "     │"
echo "     ├── server/"
echo "     │   ├── venv/              (Python 환경)"
echo "     │   ├── collector/"
echo "     │   │   ├── collector.py"
echo "     │   │   ├── models.py"
echo "     │   │   └── schema.sql"
echo "     │   └── requirements.txt"
echo "     │"
echo "     ├── shared/                (공유 정의)"
echo "     └── setup.sh               (이 스크립트)"
echo ""
echo "================================================"
