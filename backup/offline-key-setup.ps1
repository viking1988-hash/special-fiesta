<# Owner-operated Windows procedure. Never run in Railway, CI or an agent workspace.
   Only NEW task files are written/removed. Two independent USB disks required.
   Private identity is passphrase-encrypted before either offline copy is made.
   BitLocker on the trusted machine's work volume must already be active.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z]$')][string]$DriveA,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z]$')][string]$DriveB,
    [switch]$OwnerOfflineKeySetup
)
$ErrorActionPreference = 'Stop'
if (-not $OwnerOfflineKeySetup) { throw 'OWNER_OFFLINE_KEY_SETUP_REQUIRED' }
if ($env:RAILWAY_PROJECT_ID -or $env:GITHUB_ACTIONS -or $env:CI) { throw 'REMOTE_KEY_GENERATION_REFUSED' }
foreach ($tool in @('age','age-keygen')) { $null = Get-Command $tool -ErrorAction Stop }
# No network or disk encryption setting is changed by this procedure.
$defaultRoutes = @(Get-NetRoute -ErrorAction Stop | Where-Object {
    $_.DestinationPrefix -in @('0.0.0.0/0','::/0')
})
if ($defaultRoutes.Count -gt 0) { throw 'DISCONNECT_NETWORK_BEFORE_KEY_SETUP' }
$localRoot = [System.IO.Path]::GetPathRoot($env:LOCALAPPDATA)
$volume = Get-BitLockerVolume -MountPoint $localRoot -ErrorAction Stop
if ([string]$volume.VolumeStatus -ne 'FullyEncrypted' -or [string]$volume.ProtectionStatus -ne 'On') {
    throw 'TRUSTED_WORK_VOLUME_ENCRYPTION_REQUIRED'
}
$diskA = Get-Partition -DriveLetter $DriveA | Get-Disk
$diskB = Get-Partition -DriveLetter $DriveB | Get-Disk
if ([string]$diskA.BusType -ne 'USB' -or [string]$diskB.BusType -ne 'USB' -or $diskA.Number -eq $diskB.Number) {
    throw 'TWO_INDEPENDENT_USB_DISKS_REQUIRED'
}
$rootA = $DriveA.ToUpper() + ':\'
$rootB = $DriveB.ToUpper() + ':\'
if (-not (Test-Path -LiteralPath $rootA) -or -not (Test-Path -LiteralPath $rootB)) { throw 'USB_NOT_READY' }
$id = [guid]::NewGuid().ToString('N')
$name = 'Avtohirurg-age-' + $id
$work = Join-Path $env:LOCALAPPDATA $name
$copyDirs = @((Join-Path $rootA $name), (Join-Path $rootB $name))
foreach ($path in @($work) + $copyDirs) {
    if (Test-Path -LiteralPath $path) { throw 'EXISTING_KEY_DIRECTORY_REFUSED' }
}
$null = New-Item -ItemType Directory -Path $work
$sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$null = & icacls.exe $work /inheritance:r /grant:r (('*' + $sid) + ':(OI)(CI)F')
if ($LASTEXITCODE -ne 0) { throw 'PRIVATE_WORK_DIRECTORY_ACL_FAILED' }
$identity = Join-Path $work 'identity.agekey'
$sealed = Join-Path $work 'identity.agekey.age'
$cipher = Join-Path $work 'artificial.txt.age'
try {
    & age-keygen -o $identity 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'KEY_GENERATION_FAILED' }
    $recipient = (& age-keygen -y $identity 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or $recipient -notmatch '^age1[0-9a-z]+$') { throw 'PUBLIC_RECIPIENT_FAILED' }
    Write-Host 'Enter a strong, separately stored passphrase in the age prompt. Never paste it into chat.'
    & age -p -o $sealed $identity
    if ($LASTEXITCODE -ne 0) { throw 'IDENTITY_ENCRYPTION_FAILED' }
    $sealedHash = (Get-FileHash -LiteralPath $sealed -Algorithm SHA256).Hash
    $plain = Join-Path $work 'artificial.txt'
    [System.IO.File]::WriteAllBytes($plain, [System.Text.Encoding]::UTF8.GetBytes('ARTIFICIAL KEY RECOVERY ONLY'))
    $plainHash = (Get-FileHash -LiteralPath $plain -Algorithm SHA256).Hash
    & age -r $recipient -o $cipher $plain
    if ($LASTEXITCODE -ne 0) { throw 'ARTIFICIAL_ENCRYPTION_FAILED' }
    foreach ($dir in $copyDirs) {
        $null = New-Item -ItemType Directory -Path $dir
        $destination = Join-Path $dir 'identity.agekey.age'
        Copy-Item -LiteralPath $sealed -Destination $destination
        if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ne $sealedHash) { throw 'OFFLINE_COPY_HASH_MISMATCH' }
        Set-Content -LiteralPath (Join-Path $dir 'recipient.txt') -Value $recipient -Encoding ASCII
        Set-Content -LiteralPath (Join-Path $dir 'manifest.txt') -Value @(('age-key-id=' + $id), ('encrypted-identity-sha256=' + $sealedHash)) -Encoding ASCII
    }
    # Remove the original BEFORE proving recovery using each offline copy.
    Remove-Item -LiteralPath $identity -Force
    $index = 0
    foreach ($dir in $copyDirs) {
        $index++
        $recovered = Join-Path $work ('recovered-' + $index + '.agekey')
        $decoded = Join-Path $work ('decoded-' + $index + '.txt')
        & age -d -o $recovered (Join-Path $dir 'identity.agekey.age')
        if ($LASTEXITCODE -ne 0) { throw 'OFFLINE_IDENTITY_RECOVERY_FAILED' }
        $recoveredRecipient = (& age-keygen -y $recovered 2>$null).Trim()
        if ($LASTEXITCODE -ne 0 -or $recoveredRecipient -ne $recipient) { throw 'OFFLINE_RECIPIENT_MISMATCH' }
        & age -d -i $recovered -o $decoded $cipher
        if ($LASTEXITCODE -ne 0 -or (Get-FileHash -LiteralPath $decoded -Algorithm SHA256).Hash -ne $plainHash) {
            throw 'OFFLINE_ARTIFICIAL_DECRYPT_FAILED'
        }
        Remove-Item -LiteralPath $recovered,$decoded -Force
    }
    Write-Host 'OFFLINE_PRODUCTION_KEY_CUSTODY_OK independent_usb_disks=2 copies=ENCRYPTED original_removed=YES both_recoveries=PASS artificial_decrypt=PASS'
    Write-Host ('PUBLIC_RECIPIENT=' + $recipient)
    Write-Host ('KEY_ID=' + $id)
    Write-Host 'Safely eject both USB drives and store them separately. Keep the passphrase in separate protected custody.'
} finally {
    # Only this unique NEW local task directory; never remove either USB copy.
    Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
}
