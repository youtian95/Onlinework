import hashlib
import random

def get_stable_rng(key_string: str) -> random.Random:
    """
    根据输入的字符串生成一个确定的随机数生成器 (RNG)。
    只要输入字符串一样，生成的随机序列就永远一样。
    """
    # 使用 md5 将字符串转换成一个巨大的整数
    hash_object = hashlib.md5(key_string.encode('utf-8'))
    seed_int = int(hash_object.hexdigest(), 16)
    
    # 使用这个整数作为种子初始化 Random
    return random.Random(seed_int)
