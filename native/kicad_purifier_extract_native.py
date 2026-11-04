"""Compile the pinned original compatibility method without the GUI translation unit."""

import sys
from pathlib import Path

text = Path(sys.argv[1]).read_text()
start = text.index("void PLUGIN_CONTENT_MANAGER::PreparePackage(")
end = text.index("\n\nconst std::vector<PCM_PACKAGE>&", start)
print('#include "pcm.h"\n#include <wx/tokenzr.h>')
print(text[start:end])
if len(sys.argv) > 2:
    tasks = Path(sys.argv[2]).read_text()
    start = tasks.index("bool PCM_TASK_MANAGER::extract(")
    end = tasks.index(
        "\n\nPCM_TASK_MANAGER::STATUS PCM_TASK_MANAGER::InstallFromFile", start
    )
    print('#include "headless.hpp"')
    print(tasks[start:end])
