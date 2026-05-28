from app.clients import create_backend_client

from .cart_tool import CartTool
from .catalog_tool import CatalogTool
from .knowledge_tool import KnowledgeTool
from .order_tool import OrderTool
from .recommendation_tool import RecommendationTool
from .support_tool import SupportTool


class ToolRegistry:
    def __init__(self) -> None:
        client = create_backend_client()
        self.catalog = CatalogTool(client)
        self.recommendation = RecommendationTool(client)
        self.cart = CartTool(client)
        self.order = OrderTool(client)
        self.support = SupportTool(client)
        self.knowledge = KnowledgeTool(client)


__all__ = [
    "CartTool",
    "CatalogTool",
    "KnowledgeTool",
    "OrderTool",
    "RecommendationTool",
    "SupportTool",
    "ToolRegistry",
]
