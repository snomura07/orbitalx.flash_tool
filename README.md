## 前提
COMポートがバインドできない都合で、powershell上から実行する

## python
### version
    3.11.9

### python tools
```
pip3 install --no-cache-dir PyQt6==6.7.0
pip3 install pyinstaller
```

## STM32
### STM32CubeProgrammer
    事前にインストールのこと。インストールフォルダ内の、
    C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe
    を使用するので、binまでのパスを通すこと。

### path追加
    1. win + Rで、「sysdm.cpl」を起動

    2. 詳細設定 > 環境変数 > システム環境変数 > Path > 編集 > 新規

    3. STM32CubeProgrammerのbinまでのpathを追加（C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\binなど）

    4. pyinstallerのpathも追加（ C:\Users\nomura\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\Scriptsなど）

    5. powershellの再起動

## ツール
### main.py
    処理本体。python3で起動。
    config.iniで、COMの初期値とelfのパスを設定できる。

### ビルド
    - pyinstaller --onefile --windowed --distpath . main.py
    - カレント配下にexeが作成される。iniの指定が面倒なので、iniと同階層に作成する方針。
