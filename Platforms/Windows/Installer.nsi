!define UNINST_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\Frontline"

Name "Titanfall Frontline"
OutFile "Frontline-Setup.exe"
RequestExecutionLevel user
InstallDir "$LOCALAPPDATA\TF Reclaimed\Frontline"

!include "MUI2.nsh"

!define MUI_ABORTWARNING

!define MUI_FINISHPAGE_RUN "$INSTDIR\Frontline.exe"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Frontline now"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
	SetOutPath "$INSTDIR"

	File /r "${SOURCE_PATH}\*.*"

	WriteUninstaller "$INSTDIR\Uninstall.exe"

	WriteRegStr HKCU "${UNINST_KEY}" "DisplayName" "Frontline"
	WriteRegStr HKCU "${UNINST_KEY}" "UninstallString" "$INSTDIR\Uninstall.exe"
	WriteRegStr HKCU "${UNINST_KEY}" "Publisher" "TF Reclaimed"

	CreateShortcut "$SMPROGRAMS\Frontline.lnk" "$INSTDIR\Frontline.exe"
	CreateShortcut "$DESKTOP\Frontline.lnk" "$INSTDIR\Frontline.exe"
SectionEnd

Section "Uninstall"
	RMDir /r "$INSTDIR"

	Delete "$DESKTOP\Frontline.lnk"
	Delete "$SMPROGRAMS\Frontline.lnk"

	DeleteRegKey HKCU "${UNINST_KEY}"
SectionEnd