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
function Add-Mount {
    param (
        [string] $source,
        [string] $target
    )

    $mount = "--mount type=bind,source={0},target={1}" -f $source, $target
    if ($mounts -NotContains $mount) {
        $mounts.Add($mount)
    }
}

$algobattleArgs = New-Object System.Collections.Generic.List[System.Object]
Add-Mount (Convert-Path "~/.algobattle_logs") "/root/.algobattle_logs"
for ($i = 0; $i -lt $args.Length; $i++) {
    if ($args[$i] -like "*/*" -Or $args[$i] -like "*\*") {
        if ($args[$i] -like "-*=*") {
            $prefix, $rest = $args[$i] -split "=", 2
            $paths = $rest -split ","
            $containerPaths = New-Object System.Collections.Generic.List[System.Object]
            for ($j = 0; $j -lt $paths.Length; $j++) {
                $path = (Force-Convert-Path $paths[$j])
                $linuxPath = ("/docker_mounts/" + $path.Replace(":", "").Replace("\", "/"))
                Add-Mount $path $linuxPath
                $containerPaths.Add($linuxPath)
            }
            $algobattleArgs.Add(("{0}={1}" -f $prefix, $containerPaths -join ","))
        } else {
            $path = (Force-Convert-Path $args[$i])
            $linuxPath = ("/docker_mounts/" + $path.Replace(":", "").Replace("\", "/"))
            Add-Mount $path $linuxPath
            $algobattleArgs.Add($linuxPath)
        }
    } else {
        $algobattleArgs.Add(($args[$i]))
    }
}
$mounts = $mounts -join " "
$algobattleArgs = $algobattleArgs -join " "
$cmd = "docker run -ti --rm -v //var/run/docker.sock:/var/run/docker.sock {0} algobattle {1}" -f $mounts, $algobattleArgs
Invoke-Expression $cmd