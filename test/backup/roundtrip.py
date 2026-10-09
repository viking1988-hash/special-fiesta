"""CI-only transport double over an ACTUAL age archive; no live cloud claims."""
from pathlib import Path
import sys
from test_transport import FakeDisk, y

source, destination = map(Path, sys.argv[1:])
destination.parent.mkdir(mode=0o700, exist_ok=True)
disk = FakeDisk()
sha = disk.upload(source)
disk.download(source.name, destination, sha)
assert y.digest(source) == y.digest(destination)
print("SYNTHETIC_MOCK_TRANSPORT_READBACK_OK")
