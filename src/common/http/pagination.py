from rest_framework.pagination import PageNumberPagination

from common.http.response import envelope_response


class DefaultPageNumberPagination(PageNumberPagination):
    """
    符合 tech.md §3.9.2 的分页格式。
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_paginated_response(self, data):
        page_size = self.get_page_size(self.request) or self.page_size
        payload = {
            "items": data,
            "page": self.page.number,
            "page_size": page_size,
            "total": self.page.paginator.count,
        }
        return envelope_response(payload, request=self.request)
