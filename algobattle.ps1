function Force-Convert-Path {
    <#
    .SYNOPSIS
        Calls Resolve-Path but works for files that don't exist.
    .REMARKS
        From http://devhawk.net/blog/2010/1/22/fixing-powershells-busted-resolve-path-cmdlet
    #>
    param (
        [string] $FileName
    )

    $FileName = Convert-Path $FileName -ErrorAction SilentlyContinue `
                                       -ErrorVariable _frperror
    if (-not($FileName)) {
        $FileName = $_frperror[0].TargetObject
    }

    return $FileName
}


$mounts = New-Object System.Collections.Generic.List[System.Object]
$algobattleArgs = New-Object System.Collections.Generic.List[System.Object]

for ($i = 0; $i -lt $args.Length; $i++) {
    if ($args[$i] -like "*/*" -Or $args[$i] -like "*\*") {
        if ($args[$i] -like "-*=*") {
            $prefix, $rest = $args[$i] -split "=", 2
            $paths = $rest -split ","
            $containerPaths = New-Object System.Collections.Generic.List[System.Object]
            for ($j = 0; $j -lt $paths.Length; $j++) {
                $path = (Force-Convert-Path $paths[$j])
                $linuxPath = $path.Replace(":", "").Replace("\", "/")
                $mounts.Add(("--mount type=bind,source={0},target=/docker_mounts/{1}" -f $path, $linuxPath))
                $containerPaths.Add("/docker_mounts/{0}" -f $linuxPath)
            }
            $containerPaths = $containerPaths -join ","
            $algobattleArgs.Add("$($prefix)=$($containerPaths)")
        } else {
            $path = (Force-Convert-Path $args[$i])
            $linuxPath = $path.Replace(":", "").Replace("\", "/")
            Write-Output $path
            Write-Output $linuxPath
            $mounts.Add(("--mount type=bind,source={0},target=/docker_mounts/{1}" -f $path, $linuxPath))
            $algobattleArgs.Add("/docker_mounts/{0}" -f $linuxPath)
        }
    } else {
        $algobattleArgs.Add(($args[$i]))
    }
}
$mounts = $mounts -join " "
$algobattleArgs = $algobattleArgs -join " "
$logs = Convert-Path "~/.algobattle_logs"
$cmd = "docker run -ti --rm -v //var/run/docker.sock:/var/run/docker.sock --mount type=bind,source={0},target=/~/.algobattle_logs {1} algobattle {2}" -f $logs, $mounts, $algobattleArgs
Write-Output $cmd
Invoke-Expression $cmd