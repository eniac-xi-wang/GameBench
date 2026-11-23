"""Kernel CPU/file limits apply even to local policy workers."""
import os
import resource
import sys

cpu=int(sys.argv[1])
resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu))
resource.setrlimit(resource.RLIMIT_FSIZE,(4*1024**2,4*1024**2))
resource.setrlimit(resource.RLIMIT_NOFILE,(64,64))
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
os.execv(sys.argv[2],[sys.argv[2],'--max-old-space-size=256',*sys.argv[3:]])
