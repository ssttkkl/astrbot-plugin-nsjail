import os
import json
import hashlib
from astrbot.api import logger


class UidMapper:
    """UID 映射管理器"""
    def __init__(self, uid_map_file: str):
        self.uid_map_file = uid_map_file
        self.uid_map = self._load_uid_map()
    
    def _load_uid_map(self) -> dict:
        if os.path.exists(self.uid_map_file):
            try:
                with open(self.uid_map_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"加载 UID 映射失败: {e}")
        return {}
    
    def _save_uid_map(self):
        try:
            os.makedirs(os.path.dirname(self.uid_map_file), exist_ok=True)
            with open(self.uid_map_file, 'w') as f:
                json.dump(self.uid_map, f)
        except Exception as e:
            logger.error(f"保存 UID 映射失败: {e}")
    
    def get_uid_for_session(self, session_id: str) -> int:
        if session_id in self.uid_map:
            return self.uid_map[session_id]
        
        hash_value = int(hashlib.sha256(session_id.encode()).hexdigest()[:8], 16)
        candidate_uid = 10000 + (hash_value % 50000)
        
        while candidate_uid in self.uid_map.values():
            candidate_uid = (candidate_uid + 1) % 60000
            if candidate_uid < 10000:
                candidate_uid = 10000
        
        self.uid_map[session_id] = candidate_uid
        self._save_uid_map()
        return candidate_uid
