#!/bin/bash
echo "📦 Downloading Vosk model..."
DATA_DIR="${DATA_DIR:-/app/data}"
mkdir -p "$DATA_DIR"
if [ ! -d "$DATA_DIR/ru" ]; then
    cd "$DATA_DIR"
    wget -q 
https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip
    unzip -q vosk-model-small-ru-0.22.zip
    mv vosk-model-small-ru-0.22 ru
    rm vosk-model-small-ru-0.22.zip
    echo "✅ Model downloaded"
else
    echo "✅ Model exists"
fi#!/bin/bash
echo "📦 Downloading Vosk Russian model..."
mkdir -p models
cd models
if [ ! -d "ru" ]; then
    wget -q 
https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip
    unzip -q vosk-model-small-ru-0.22.zip
    mv vosk-model-small-ru-0.22 ru
    rm vosk-model-small-ru-0.22.zip
    echo "✅ Model downloaded"
else
    echo "✅ Model already exists"
fi
