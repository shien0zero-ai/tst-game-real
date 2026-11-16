param([string]$ProjectRoot=(Split-Path $PSScriptRoot -Parent))
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$source=Join-Path $ProjectRoot 'SourceArt\Viewmodel\Service\textures\service_pistol_arm_4k.jpg'
$dest=Join-Path $ProjectRoot 'SourceArt\FieldFinish\arm-samples.bin'
New-Item -ItemType Directory -Force -Path (Split-Path $dest -Parent) | Out-Null
$bitmap=New-Object Drawing.Bitmap($source)
$stream=[IO.File]::Create($dest)
$writer=New-Object IO.BinaryWriter($stream)
try {
 $writer.Write([int]256);$writer.Write([int]256)
 for($y=0;$y -lt 256;$y++){for($x=0;$x -lt 256;$x++){
  $color=$bitmap.GetPixel([int](($x+.5)*$bitmap.Width/256),[int](($y+.5)*$bitmap.Height/256))
  $writer.Write([byte]$color.R);$writer.Write([byte]$color.G);$writer.Write([byte]$color.B)
 }}
} finally {$writer.Close();$bitmap.Dispose()}
Write-Output 'Original ARM texture sampled for geometry material classification; original image unchanged.'
