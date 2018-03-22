@echo OFF
REM="""
setlocal
set PythonExe=""
set PythonExeFlags=

for %%i in (cmd bat exe) do (
    for %%j in (python.%%i) do (
        call :SetPythonExe "%%~$PATH:j"
    )
)
for /f "tokens=2 delims==" %%i in ('assoc .py') do (
    for /f "tokens=2 delims==" %%j in ('ftype %%i') do (
        for /f "tokens=1" %%k in ("%%j") do (
            call :SetPythonExe %%k
        )
    )
)
%PythonExe% -x %PythonExeFlags% "%~f0" %*
exit /B %ERRORLEVEL%
goto :EOF

:SetPythonExe
if not ["%~1"]==[""] (
    if [%PythonExe%]==[""] (
        set PythonExe="%~1"
    )
)
goto :EOF
"""

# ===================================================
# Python script starts here
# Above helper adapted from https://github.com/aws/aws-cli/blob/1.11.121/bin/aws.cmd
# ===================================================

#!/usr/bin/env python

from stacker.logger import setup_logging
from stacker.commands import Stacker

if __name__ == "__main__":
    stacker = Stacker(setup_logging=setup_logging)
    args = stacker.parse_args()
    stacker.configure(args)
    args.run(args)
