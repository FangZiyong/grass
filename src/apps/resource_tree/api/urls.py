"""
resource_tree API URL 配置

路由前缀由 api/v1/urls.py 统一挂载。
"""
from django.urls import path

from apps.resource_tree.api.views_tree import ChildrenView, FolderCreateView, MoveNodeView, RenameNodeView

app_name = "resource_tree"

urlpatterns = [
    # GET /api/resource-trees/{scope}/children
    path(
        "resource-trees/<str:scope>/children",
        ChildrenView.as_view(),
        name="children",
    ),
    # POST /api/resource-trees/{scope}/folders
    path(
        "resource-trees/<str:scope>/folders",
        FolderCreateView.as_view(),
        name="create_folder",
    ),
    # PATCH /api/resource-trees/{scope}/nodes/{node_id} (重命名)
    path(
        "resource-trees/<str:scope>/nodes/<int:node_id>",
        RenameNodeView.as_view(),
        name="rename_node",
    ),
    # POST /api/resource-trees/{scope}/move (移动节点)
    path(
        "resource-trees/<str:scope>/move",
        MoveNodeView.as_view(),
        name="move_node",
    ),
    # POST /api/resource-trees/{scope}/reorder
    # TODO: 实现 ReorderView（任务 T4.6）
    # path(
    #     "resource-trees/<str:scope>/reorder",
    #     ReorderView.as_view(),
    #     name="reorder",
    # ),
]
