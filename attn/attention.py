import torch
from torch import nn, Tensor
import torch.nn.functional as F


class Attention(nn.Module):
    def __init__(self, word_size:int=512, embed_dim:int=64) -> None:
        super().__init__()
        self.embed_dim = embed_dim
        self.dim_K = torch.tensor(embed_dim)
        self.query = nn.Linear(in_features=word_size, out_features=embed_dim, bias=True)
        self.key  = nn.Linear(in_features=word_size, out_features=embed_dim, bias=True)
        self.value = nn.Linear(in_features=word_size, out_features=embed_dim, bias=True)

    def self_attention(self, Q: Tensor, K: Tensor, V: Tensor) -> Tensor:
        """
        Perform self-attention on the input tensors.

        This is a simple implementation of self-attention that uses the dot product attention mechanism.
        If you are looking for attention with better performance, please try:

        * `F.scaled_dot_product_attention`
        * [Flash Attention](https://github.com/Dao-AILab/flash-attention)

        Args:
            Q: The query tensor.
            K: The key tensor.
            V: The value tensor.

        Returns:
            The output tensor of the self-attention layer.
        """

        K_T = torch.transpose(K, 0, 1)
        score = torch.matmul(Q, K_T)
        score /= torch.sqrt(self.dim_K)
        score = torch.softmax(score, dim=-1)
        Z = torch.matmul(score, V)
        return Z

    def forward(self, x:Tensor) -> Tensor:
        Q = self.query(x)
        K = self.key(x)
        V = self.value(x)
        Z = self.self_attention(Q, K, V)
        # Z = F.scaled_dot_product_attention(Q, K, V)
        return Z


class MultiheadAttention(nn.Module):
    r"""
    https://arxiv.org/abs/1706.03762
    """
    def __init__(self, word_size: int = 512, embed_dim: int = 64, n_head:int=8) -> None:
        super().__init__()
        self.n_head = n_head
        self.embed_dim = embed_dim
        self.dim_K = torch.tensor(embed_dim)
        self.proj = nn.Parameter(torch.empty(embed_dim * n_head, embed_dim))
        nn.init.xavier_uniform_(self.proj)
        self.multihead = nn.ModuleList([
            Attention(word_size, embed_dim) for _ in range(n_head)
        ])

    def forward(self, x: Tensor) -> Tensor:
        Z_s = torch.cat([head(x) for head in self.multihead], dim=1)
        Z = torch.matmul(Z_s, self.proj)
        return Z


class  MultiQueryAttention(Attention):
    r"""
    https://arxiv.org/pdf/1911.02150.pdf
    """
    def __init__(self, word_size: int = 512, embed_dim: int = 64, n_query:int=8) -> None:
        super().__init__(word_size, embed_dim)
        self.n_query = n_query
        self.proj = nn.Parameter(torch.empty(embed_dim * n_query, embed_dim))
        nn.init.xavier_normal_(self.proj)
        delattr(self, 'query')
        self.querys = nn.ModuleList([
            nn.Linear(in_features=word_size, out_features=embed_dim, bias=True)
            for _ in range(n_query)
        ])
        self.key = nn.Linear(in_features=word_size, out_features=embed_dim, bias=True)
        self.value = nn.Linear(in_features=word_size, out_features=embed_dim, bias=True)

    def forward(self, x: Tensor) -> Tensor:
        K = self.key(x)
        V = self.value(x)
        Z_s = torch.cat([
            self.self_attention(query(x), K, V) for query in self.querys
        ], dim=1)
        Z = torch.matmul(Z_s, self.proj)
        return Z


class  GroupedQueryAttention(Attention):
    r"""
    https://arxiv.org/pdf/2305.13245.pdf
    """
    def __init__(self, word_size: int = 512, embed_dim: int = 64,
                 n_grouped: int = 4, n_query_each_group:int=2) -> None:
        super().__init__(word_size, embed_dim)
        delattr(self, 'query')
        delattr(self, 'key')
        delattr(self, 'value')

        self.grouped = nn.ModuleList([
            MultiQueryAttention(word_size, embed_dim, n_query=n_query_each_group)
            for _ in range(n_grouped)
        ])
        # self.proj = nn.Parameter(torch.empty((..., ...), requires_grad=True))
        self.proj = nn.Parameter(torch.empty(embed_dim * n_grouped, embed_dim))
        nn.init.xavier_uniform_(self.proj)

    def forward(self, x: Tensor) -> Tensor:
        Z_s = torch.cat([head(x) for head in self.grouped], dim=1)
        Z = torch.matmul(Z_s, self.proj)
        return Z
