import json
import os
import logging
import docker

logger = logging.getLogger(__name__)

class BlacklistManager:
    def __init__(self, data_dir="/watchtower-data", docker_socket_path="/var/run/docker.sock"):
        self.data_dir = data_dir
        self.blacklist_file = os.path.join(data_dir, "blacklist.json")
        self.docker_client = docker.DockerClient(base_url=f'unix://{docker_socket_path}')
        self._ensure_data_dir()
        self.blacklist = self._load_blacklist()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            logger.info(f"创建数据目录: {self.data_dir}")

    def _load_blacklist(self):
        """加载黑名单"""
        try:
            if os.path.exists(self.blacklist_file):
                with open(self.blacklist_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"加载黑名单失败: {e}")
            return []

    def _save_blacklist(self):
        """保存黑名单"""
        try:
            with open(self.blacklist_file, 'w', encoding='utf-8') as f:
                json.dump(self.blacklist, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"保存黑名单失败: {e}")
            return False

    def add_to_blacklist(self, container_name):
        """添加容器到黑名单"""
        try:
            # 检查容器是否存在
            container = self.docker_client.containers.get(container_name)
            
            if container_name not in self.blacklist:
                self.blacklist.append(container_name)
                if self._save_blacklist():
                    # 为容器添加标签，告诉 Watchtower 忽略此容器
                    labels = container.labels or {}
                    labels['com.centurylinklabs.watchtower.enable'] = 'false'
                    
                    # 更新容器配置
                    container.update(labels=labels)
                    logger.info(f"已添加容器到黑名单并设置标签: {container_name}")
                    return True
            return False
        except docker.errors.NotFound:
            logger.error(f"容器不存在: {container_name}")
            return False
        except Exception as e:
            logger.error(f"添加黑名单失败: {e}")
            return False

    def remove_from_blacklist(self, container_name):
        """从黑名单中移除容器"""
        try:
            # 检查容器是否存在
            container = self.docker_client.containers.get(container_name)
            
            if container_name in self.blacklist:
                self.blacklist.remove(container_name)
                if self._save_blacklist():
                    # 移除容器的忽略标签
                    labels = container.labels or {}
                    if 'com.centurylinklabs.watchtower.enable' in labels:
                        del labels['com.centurylinklabs.watchtower.enable']
                    
                    # 更新容器配置
                    container.update(labels=labels)
                    logger.info(f"已从黑名单移除容器并清除标签: {container_name}")
                    return True
            return False
        except docker.errors.NotFound:
            logger.error(f"容器不存在: {container_name}")
            return False
        except Exception as e:
            logger.error(f"移除黑名单失败: {e}")
            return False

    def get_blacklist(self):
        """获取黑名单列表"""
        return self.blacklist.copy()

    def is_blacklisted(self, container_name):
        """检查容器是否在黑名单中"""
        return container_name in self.blacklist

    def clear_blacklist(self):
        """清空黑名单"""
        try:
            # 清除所有容器的忽略标签
            for container_name in self.blacklist:
                try:
                    container = self.docker_client.containers.get(container_name)
                    labels = container.labels or {}
                    if 'com.centurylinklabs.watchtower.enable' in labels:
                        del labels['com.centurylinklabs.watchtower.enable']
                    container.update(labels=labels)
                except docker.errors.NotFound:
                    continue
                except Exception as e:
                    logger.error(f"清除容器标签失败 {container_name}: {e}")
            
            self.blacklist.clear()
            return self._save_blacklist()
        except Exception as e:
            logger.error(f"清空黑名单失败: {e}")
            return False

# 全局黑名单管理器实例
blacklist_manager = BlacklistManager()
