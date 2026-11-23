"""Apply kernel process limits before starting an evaluated policy."""
import os
import resource
import sys

resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
resource.setrlimit(resource.RLIMIT_FSIZE, (4 * 1024**2, 4 * 1024**2))
resource.setrlimit(resource.RLIMIT_NOFILE, (96, 96))
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
os.execv(sys.argv[1], [sys.argv[1], '--max-old-space-size=256', *sys.argv[2:]])
