$ErrorActionPreference = 'Stop'
$PatchDir = (Resolve-Path $PSScriptRoot).Path
$OutputDir = Join-Path $PatchDir 'oneclick-out'
$WorkDir = Join-Path $PatchDir 'oneclick-build'
$SetupPath = Join-Path $PatchDir 'Momodora2ZH_Setup.exe'
& py -3 -c "import sys,platform,zlib,PyInstaller; assert sys.maxsize>2**32; assert platform.python_version()=='3.12.6'; assert zlib.ZLIB_VERSION=='1.3.1'; assert PyInstaller.__version__=='6.22.3'"
if ($LASTEXITCODE -ne 0) { throw 'Build requires Python 3.12.6 x64, zlib 1.3.1 and PyInstaller 6.22.3.' }
Remove-Item -LiteralPath $SetupPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path $OutputDir 'Momodora2ZH_Setup.exe') -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Path $OutputDir,$WorkDir -Force | Out-Null
$Tools = Join-Path $PatchDir 'tools'
$Args = @('-3','-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed',
  '--name','Momodora2ZH_Setup','--distpath',$OutputDir,'--workpath',$WorkDir,'--specpath',$WorkDir,
  '--paths',$PatchDir,'--paths',$Tools,'--hidden-import','oneclick_core','--hidden-import','apply_patch',
  '--hidden-import','gm7_momo2','--hidden-import','tkinter','--hidden-import','tkinter.ttk',
  '--hidden-import','tkinter.filedialog','--hidden-import','tkinter.messagebox',
  '--icon',(Join-Path $PatchDir 'assets\launcher.ico'),
  '--add-data',((Join-Path $PatchDir 'patch.json')+';.'),
  '--add-data',((Join-Path $PatchDir 'assets\momo2_zh_text.png')+';assets'),
  '--add-data',((Join-Path $PatchDir 'assets\momo2_zh_ctrl.png')+';assets'),
  '--add-data',((Join-Path $PatchDir 'assets\atlas_layout.json')+';assets'),
  '--add-data',((Join-Path $PatchDir 'Licenses')+';Licenses'),
  (Join-Path $PatchDir 'launcher.py'))
& py @Args
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
$Built = Join-Path $OutputDir 'Momodora2ZH_Setup.exe'
if (-not (Test-Path $Built)) { throw 'Expected standalone EXE was not created.' }
Copy-Item -LiteralPath $Built -Destination $SetupPath -Force
$Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $SetupPath).Hash.ToLowerInvariant()
$Size = (Get-Item -LiteralPath $SetupPath).Length
$Report = [ordered]@{
  product = 'Momodora II v041 Simplified Chinese Installer'
  version = '0.1.0'
  file = 'Momodora2ZH_Setup.exe'
  architecture = 'x64'
  one_file = $true
  python_required_on_target = $false
  pyinstaller = '6.22.3'
  python_build_version = '3.12.6'
  size_bytes = $Size
  sha256 = $Sha
}
$Report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PatchDir 'oneclick_build_report.json') -Encoding utf8
Set-Content -LiteralPath (Join-Path $PatchDir 'Momodora2ZH_Setup.exe.sha256') -Value "$Sha  Momodora2ZH_Setup.exe" -Encoding ascii
Write-Host "Built $SetupPath ($Size bytes)"
Write-Host "SHA256 $Sha"
