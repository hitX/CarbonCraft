Write-Host "Starting PyInstaller build for CarbonCraft..."

$pyCmd = 'pyinstaller main.py --onedir --windowed --name=CarbonCraft --icon=textures/ursina.ico --hidden-import=rdkit --hidden-import=rdkit.Chem --hidden-import=rdkit.Chem.AllChem --hidden-import=pubchempy --hidden-import=ursina --hidden-import=panda3d --hidden-import=panda3d.core --collect-all rdkit --collect-all ursina --collect-all pubchempy --collect-all panda3d --collect-all panda3d_gltf --collect-all panda3d_simplepbr --collect-data ursina --add-data "textures/ursina.ico;textures"'

Write-Host "Command: $pyCmd"

Invoke-Expression $pyCmd

if ($LASTEXITCODE -eq 0) {
    Write-Host "PyInstaller finished successfully. See the 'dist\CarbonCraft' folder." -ForegroundColor Green
} else {
    Write-Host "PyInstaller returned exit code $LASTEXITCODE" -ForegroundColor Red
}

pause
