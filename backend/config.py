"""
统一环境变量配置
所有配置项集中管理，启动时校验必填项。
"""
import os


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

    # ===== 派生属性 =====

    @property
    def payjs_enabled(self) -> bool:
        """PayJS 是否配置完整"""
        return bool(self.PAYJS_MCHID and self.PAYJS_KEY)

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
        return (
            f"DATABASE_URL: {self.DATABASE_URL}\n"
            f"JWT_SECRET: {'***' + self.JWT_SECRET[-4:] if len(self.JWT_SECRET) > 4 else '(empty)'}\n"
            f"ASSETS_DIR: {self.ASSETS_DIR}\n"
            f"PayJS: {'✅ enabled' if self.payjs_enabled else '❌ disabled (mock mode)'}\n"
        )


settings = Settings()
