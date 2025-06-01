@echo off
setlocal enabledelayedexpansion

REM --- CONFIGURATION ---
set "INPUT_DIR=D:\Personal\Books\puranas"
set "OUTPUT_DIR=%INPUT_DIR%\OCR"
set "TEMP_DIR=E:\temp_ocr"

if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"

REM Check for Ghostscript
where gswin64c >nul 2>&1
if %errorlevel%==0 (
    set "GSCMD=gswin64c"
) else (
    where gswin32c >nul 2>&1
    if %errorlevel%==0 (
        set "GSCMD=gswin32c"
    ) else (
        echo ❌ ERROR: Ghostscript not found in PATH. Please install Ghostscript.
        goto :eof
    )
)

REM Process each PDF file in INPUT_DIR
pushd "%INPUT_DIR%"
echo ============================================
echo Resumable OCR Script - Processing all PDFs in %INPUT_DIR%
echo Output directory:     %OUTPUT_DIR%
echo Temporary directory:  %TEMP_DIR%
echo ============================================

for %%F in (*.pdf) do (
    call :process_file "%%F"
)

popd
endlocal
echo.
echo ✅ All PDFs processed.
goto :eof

:process_file
setlocal enabledelayedexpansion
set "CURRENT_FILE=%~1"
set "PDF_NAME=%~n1"
set "TEMP_TIFF_FILE=%TEMP_DIR%\%PDF_NAME%.tif"
set "OUTPUT_PDF_FILE=%OUTPUT_DIR%\%PDF_NAME%.pdf"

echo.
echo --------------------------------------------
echo 🔍 Processing "%CURRENT_FILE%"
echo --------------------------------------------

REM Skip if output PDF already exists
if exist "%OUTPUT_PDF_FILE%" (
    echo ✅ Output PDF already exists: "%OUTPUT_PDF_FILE%" — Skipping.
    endlocal
    goto :eof
)

REM Clean temp TIFFs and PDFs for this PDF to avoid conflicts
del /q "%TEMP_DIR%\%PDF_NAME%_page_*.tif" >nul 2>&1
del /q "%TEMP_DIR%\%PDF_NAME%_page_*.pdf" >nul 2>&1

REM STEP 1: Convert PDF to individual TIFF pages with zero-padded underscore names
echo 🖨️ Converting PDF to individual TIFF pages with pdftocairo at 200 DPI...
pdftocairo -tiff -r 200 "%CURRENT_FILE%" "%TEMP_DIR%\%PDF_NAME%_page"
if errorlevel 1 (
    echo ⚠️ pdftocairo failed at 200 DPI. Trying at 150 DPI...
    pdftocairo -tiff -r 150 "%CURRENT_FILE%" "%TEMP_DIR%\%PDF_NAME%_page"
    if errorlevel 1 (
        echo ❌ ERROR: pdftocairo failed. Skipping file.
        endlocal
        goto :eof
    )
)

REM STEP 1b: Rename TIFF pages to zero-padded format (if needed)
REM Example of renaming test_page-1.tif => test_page_001.tif

echo 🔄 Renaming TIFF pages to zero-padded underscore format...
setlocal enabledelayedexpansion
set /a page_num=0
for /f "tokens=*" %%I in ('dir /b /on "%TEMP_DIR%\%PDF_NAME%_page-*.tif"') do (
    set /a page_num+=1
    set "page_padded=000!page_num!"
    set "page_padded=!page_padded:~-3!"
    ren "%TEMP_DIR%\%%I" "%PDF_NAME%_page_!page_padded!.tif"
)
endlocal & setlocal enabledelayedexpansion

REM STEP 2: Verify TIFF pages exist
dir /b "%TEMP_DIR%\%PDF_NAME%_page_*.tif" >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: No individual TIFF pages found. Expected files like %PDF_NAME%_page_001.tif
    endlocal
    goto :eof
)
echo ✂ Individual zero-padded TIFF pages found and ready for OCR.

REM STEP 3: OCR each TIFF page sequentially to produce PDFs
echo 🔠 Starting OCR for each TIFF page sequentially...
for /f "delims=" %%P in ('dir /b /on "%TEMP_DIR%\%PDF_NAME%_page_*.tif"') do (
    set "TIF_FILE=%TEMP_DIR%\%%P"
    set "BASE_NAME=%%~nP"
    set "PDF_FILE=%TEMP_DIR%\!BASE_NAME!.pdf"

    if exist "!PDF_FILE!" (
        echo   ✅ Already done: !PDF_FILE!
    ) else (
        echo   🏃 OCR: %%P
        tesseract "!TIF_FILE!" "%TEMP_DIR%\!BASE_NAME!" pdf
        if errorlevel 1 (
            echo ❌ OCR failed for %%P, skipping file.
            endlocal
            goto :eof
        )
    )
)

REM STEP 4: Merge all OCRed PDFs in correct order using Ghostscript
pushd "%TEMP_DIR%"
if exist "temp_merged_output.pdf" del "temp_merged_output.pdf"

echo 📎 Merging PDFs into final file...
set "MERGE_LIST="
for /f "delims=" %%F in ('dir /b /on "%PDF_NAME%_page_*.pdf"') do (
    set "MERGE_LIST=!MERGE_LIST! %%F"
)

%GSCMD% -dBATCH -dNOPAUSE -q -sDEVICE=pdfwrite -sOutputFile="temp_merged_output.pdf" !MERGE_LIST!
if exist "temp_merged_output.pdf" (
    move /Y "temp_merged_output.pdf" "%OUTPUT_PDF_FILE%" >nul
    echo ✅ Final PDF created: "%OUTPUT_PDF_FILE%"
) else (
    echo ❌ ERROR: Ghostscript merge failed.
)
popd

endlocal
goto :eof
