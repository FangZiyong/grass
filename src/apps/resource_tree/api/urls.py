"""
resource_tree API URL 配置

路由前缀由 api/v1/urls.py 统一挂载。
"""
from django.urls import path

from apps.resource_tree.api.views_tree import ChildrenView

app_name = "resource_tree"

urlpatterns = [
    # GET /api/resource-trees/{scope}/children
    path(
        "resource-trees/<str:scope>/children",
        ChildrenView.as_view(),
        name="children",
    ),
]
