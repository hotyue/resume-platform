"""
统一环境变量配置
所有配置项集中管理，启动时校验必填项。
"""
import os
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
load_dotenv()


class Settings:
    # ===== 必填项（生产环境必须设置） =====

    JWT_SECRET: str = os.environ.get("JWT_SECRET", "resume-platform-dev-secret-change-in-prod")
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL",
        "sqlite:///./resume_dev.db"
    )

    # ===== 可选项 =====

    ASSETS_DIR: str = os.environ.get("ASSETS_DIR", "/root/assets")

    # PayJS 支付（未设置时回退模拟支付）
    PAYJS_MCHID: str = os.environ.get("PAYJS_MCHID", "")
    PAYJS_KEY: str = os.environ.get("PAYJS_KEY", "")
    PAYJS_NOTIFY_URL: str = os.environ.get("PAYJS_NOTIFY_URL", "")

    # ===== S3 存储（群晖 NAS / 其他 S3 兼容服务） =====

    S3_ENDPOINT: str = os.environ.get("S3_ENDPOINT", "")
    S3_ACCESS_KEY: str = os.environ.get("S3_ACCESS_KEY", "")
    S3_SECRET_KEY: str = os.environ.get("S3_SECRET_KEY", "")
    S3_BUCKET: str = os.environ.get("S3_BUCKET", "resume-deliveries")
    S3_REGION: str = os.environ.get("S3_REGION", "us-east-1")

    # 交付文件配置
    DELIVERY_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    DELIVERY_ALLOWED_PDF: tuple = (".pdf",)
    DELIVERY_ALLOWED_WORD: tuple = (".doc", ".docx")

    # 默认下载链接有效期（秒）— 也可在后台配置中修改
    DEFAULT_DELIVERY_URL_EXPIRES: int = 48 * 3600  # 48 小时

    # ===== 派生属性 =====

    @property
    def payjs_enabled(self) -> bool:
        """PayJS 是否配置完整"""
        return bool(self.PAYJS_MCHID and self.PAYJS_KEY)

    @property
    def s3_enabled(self) -> bool:
        """S3 存储是否配置完整"""
        return bool(self.S3_ENDPOINT and self.S3_ACCESS_KEY and self.S3_SECRET_KEY)

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL

    @property
    def connect_args(self) -> dict:
        """SQLite 专用连接参数"""
        if self.is_sqlite:
            return {"check_same_thread": False}
        return {}

    def validate(self):
        """启动时校验必填配置"""
        errors = []
        if not self.JWT_SECRET:
            errors.append("JWT_SECRET 环境变量未设置")
        if not self.DATABASE_URL:
            errors.append("DATABASE_URL 环境变量未设置")

        if errors:
            raise RuntimeError(
                "配置错误，请设置以下环境变量：\n" +
                "\n".join(f"  - {e}" for e in errors)
            )

    def show(self) -> str:
        """打印当前配置摘要（隐藏敏感信息）"""
        s3_status = "✅ enabled" if self.s3_enabled else "❌ disabled (need S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY)"
        return (
            f"DATABASE_URL: {self.DATABASE_URL}\n"
            f"JWT_SECRET: {'***' + self.JWT_SECRET[-4:] if len(self.JWT_SECRET) > 4 else '(empty)'}\n"
            f"ASSETS_DIR: {self.ASSETS_DIR}\n"
            f"PayJS: {'✅ enabled' if self.payjs_enabled else '❌ disabled (mock mode)'}\n"
            f"S3 Storage: {s3_status}\n"
            f"  Endpoint: {self.S3_ENDPOINT or '(not set)'}\n"
            f"  Bucket: {self.S3_BUCKET}\n"
            f"  Max file size: {self.DELIVERY_MAX_SIZE // (1024*1024)}MB\n"
            f"  Default URL expires: {self.DEFAULT_DELIVERY_URL_EXPIRES // 3600}h\n"
        )


settings = Settings()
