"""
Distributed File System State

Thread-safe, CRDT-like state for a replicated file system
Conflict resolution: Last-Writer-Wins (LWW) using Lamport timestamps
"""

import os
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

Timestamp = Tuple[int, str]  # (lamport_counter, replica_id)


@dataclass
class FileEntry:
    filename: str
    content: str
    timestamp: Timestamp  # (lamport, replica_id)
    deleted: bool = False


class ThreadSafeFileState:
    """
    Thread-safe file system state with LWW conflict resolution

    Each file is tracked by its filename. When two nodes modify the
    same file concurrently, the operation with the higher Lamport
    timestamp wins, Ties are broken by replica ID (lexicographic)
    """

    def __init__(self, storage_dir: str):
        self._files: Dict[str, FileEntry] = {}
        self._lock = threading.Lock()
        self._storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)

    def apply_create(self, filename: str, content: str,
                     timestamp: Timestamp) -> bool:
        with self._lock:
            if self._should_apply(filename, timestamp):
                self._files[filename] = FileEntry(
                    filename=filename,
                    content=content,
                    timestamp=timestamp,
                    deleted=False,
                )
                self._write_to_disk(filename, content)
                return True
            return False

    def apply_write(self, filename: str, content: str,
                    timestamp: Timestamp) -> bool:
        with self._lock:
            if self._should_apply(filename, timestamp):
                self._files[filename] = FileEntry(
                    filename=filename,
                    content=content,
                    timestamp=timestamp,
                    deleted=False,
                )
                self._write_to_disk(filename, content)
                return True
            return False

    def apply_delete(self, filename: str,
                     timestamp: Timestamp) -> bool:
        with self._lock:
            if self._should_apply(filename, timestamp):
                self._files[filename] = FileEntry(
                    filename=filename,
                    content="",
                    timestamp=timestamp,
                    deleted=True,
                )
                self._remove_from_disk(filename)
                return True
            return False

    def apply_rename(self, old_name: str, new_name: str,
                     timestamp: Timestamp) -> bool:
        with self._lock:
            entry = self._files.get(old_name)
            if entry is None or entry.deleted:
                return False
            if not self._should_apply(old_name, timestamp):
                return False

            content = entry.content

            # mark old as deleted
            self._files[old_name] = FileEntry(
                filename=old_name,
                content="",
                timestamp=timestamp,
                deleted=True,
            )
            self._remove_from_disk(old_name)

            # create new
            self._files[new_name] = FileEntry(
                filename=new_name,
                content=content,
                timestamp=timestamp,
                deleted=False,
            )
            self._write_to_disk(new_name, content)
            return True

    def read_file(self, filename: str) -> Optional[str]:
        with self._lock:
            entry = self._files.get(filename)
            if entry and not entry.deleted:
                return entry.content
            return None

    def list_files(self) -> list:
        with self._lock:
            result = []
            for name, entry in sorted(self._files.items()):
                if not entry.deleted:
                    ts = entry.timestamp
                    result.append(
                        f"  {name}  (ts={ts[0]}, from={ts[1]})"
                    )
            return result

    # ── LWW conflict resolution 

    def _should_apply(self, filename: str,
                      new_ts: Timestamp) -> bool:
        existing = self._files.get(filename)
        if existing is None:
            return True
        return new_ts > existing.timestamp

    # ── Disk I/O 

    def _write_to_disk(self, filename: str, content: str):
        path = os.path.join(self._storage_dir, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True) \
            if os.path.dirname(path) else None
        with open(path, "w") as f:
            f.write(content)

    def _remove_from_disk(self, filename: str):
        path = os.path.join(self._storage_dir, filename)
        if os.path.exists(path):
            os.remove(path)
