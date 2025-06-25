#include <windows.h>
#include <iostream>
#include <string>

int main() {
    // Get the full path of the current executable
    char exePath[MAX_PATH];
    GetModuleFileName(NULL, exePath, MAX_PATH);

    // Extract the directory part from the full path
    std::string exeDir(exePath);
    size_t pos = exeDir.find_last_of("\\/");
    if (pos != std::string::npos) {
        exeDir = exeDir.substr(0, pos + 1);
    }

    // Build command line: assumes Python and script are in the same dir as exe
    std::string commandLine = "\"";
    commandLine += exeDir + "python_embed\\python.exe\" enviro_tools_gui.py";

    STARTUPINFO si = { sizeof(STARTUPINFO) };
    PROCESS_INFORMATION pi;

    BOOL success = CreateProcess(
        NULL,                           // Application name
        (LPSTR)commandLine.c_str(),     // Command line
        NULL,                           // Process security attributes
        NULL,                           // Thread security attributes
        FALSE,                          // Inherit handles
        CREATE_NEW_CONSOLE,             // Creation flags
        NULL,                           // Environment block
        exeDir.c_str(),                 // Working directory (where the script is)
        &si,                            // STARTUPINFO
        &pi                             // PROCESS_INFORMATION
    );

    if (!success) {
        std::cerr << "CreateProcess failed: " << GetLastError() << std::endl;
        return 1;
    }

    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);

    return 0;
}
