' Haft Almas - double-click launcher (works from local folders and UNC shares)
Option Explicit
Dim fso, sh, here, tmp, f, bat, rc
Set fso = CreateObject("Scripting.FileSystemObject")
Set sh = CreateObject("WScript.Shell")
here = fso.GetParentFolderName(WScript.ScriptFullName)
If Not fso.FileExists(here & "\main.py") Then
    MsgBox "main.py was not found in:" & vbCrLf & here, vbCritical, "Haft Almas"
    WScript.Quit 1
End If
' main.py reads the real (UNC) folder from this variable
sh.Environment("PROCESS")("HAFT_APP_ROOT") = here
bat = sh.ExpandEnvironmentStrings("%TEMP%") & "\haft_almas_" & Int(Rnd() * 100000) & ".bat"
Set f = fso.CreateTextFile(bat, True)
f.WriteLine "@echo off"
f.WriteLine "pushd """ & here & """"
f.WriteLine "if errorlevel 1 ("
f.WriteLine "  echo Could not open the program folder: " & here
f.WriteLine "  pause"
f.WriteLine "  exit /b 1"
f.WriteLine ")"
f.WriteLine "where py >nul 2>nul"
f.WriteLine "if not errorlevel 1 ("
f.WriteLine "  py -3 main.py"
f.WriteLine ") else ("
f.WriteLine "  python main.py"
f.WriteLine ")"
f.WriteLine "set RC=%errorlevel%"
f.WriteLine "popd"
f.WriteLine "if not ""%RC%""==""0"" pause"
f.Close
rc = sh.Run("""" & bat & """", 1, True)
On Error Resume Next
fso.DeleteFile bat
