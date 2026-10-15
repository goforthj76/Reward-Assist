param(
  [string]$Sdk = 'C:/Users/gofor/AppData/Local/Android/Sdk',
  [string]$Jdk = 'C:/Program Files/Android/Android Studio/jbr'
)
$ErrorActionPreference='Stop'
$here=$PSScriptRoot
$out=Join-Path $here 'build'
$tools=Join-Path $Sdk 'build-tools/36.1.0'
$androidJar=Join-Path $Sdk 'platforms/android-34/android.jar'
New-Item -ItemType Directory -Force $out,"$out/classes","$out/dex" | Out-Null
$env:JAVA_TOOL_OPTIONS="-Djava.io.tmpdir=$out"
function Checked([string]$exe,[string[]]$arguments) { & $exe @arguments; if($LASTEXITCODE -ne 0){throw "Build failed: $exe"} }
$sources=@(Get-ChildItem "$here/src" -Recurse -Filter '*.java' | ForEach-Object {$_.FullName})
Checked "$Jdk/bin/javac.exe" (@('-g','-encoding','UTF-8','-source','8','-target','8','-classpath',$androidJar,'-d',"$out/classes")+$sources)
Checked "$Jdk/bin/jar.exe" @('cf',"$out/classes.jar",'-C',"$out/classes",'.')
Checked "$Jdk/bin/java.exe" @('-cp',"$tools/lib/d8.jar",'com.android.tools.r8.D8','--lib',$androidJar,'--min-api','26','--output',"$out/dex","$out/classes.jar")
Checked "$tools/aapt2.exe" @('compile',"$here\res\values\strings.xml",'-o',$out)
Checked "$tools/aapt2.exe" @('link','--manifest',"$here\AndroidManifest.xml",'-I',$androidJar.Replace('/','\'),'-o',"$out\unsigned.apk","$out\values_strings.arsc.flat")
Push-Location "$out/dex"
try { Checked "$Jdk/bin/jar.exe" @('uf',"$out/unsigned.apk",'classes.dex') } finally { Pop-Location }
Checked "$tools/zipalign.exe" @('-f','4',"$out/unsigned.apk","$out/aligned.apk")
# Local preview key only. Preserve it for upgrades; never commit it.
if(!(Test-Path "$out/preview.jks")) {
  Checked "$Jdk/bin/keytool.exe" @('-genkeypair','-keystore',"$out/preview.jks",'-storepass','android','-keypass','android','-alias','preview','-keyalg','RSA','-keysize','2048','-validity','3650','-dname','CN=Reward Assist Local Preview')
}
Checked "$Jdk/bin/java.exe" @('-jar',"$tools/lib/apksigner.jar",'sign','--ks',"$out/preview.jks",'--ks-key-alias','preview','--ks-pass','pass:android','--key-pass','pass:android','--out',"$out/Reward-Assist-Wake-Relay.apk","$out/aligned.apk")
Checked "$Jdk/bin/java.exe" @('-jar',"$tools/lib/apksigner.jar",'verify',"$out/Reward-Assist-Wake-Relay.apk")
Write-Output "Built $out/Reward-Assist-Wake-Relay.apk"


