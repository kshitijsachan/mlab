import torch as t
import gpt_tests
from einops import rearrange
import torch.nn.functional as F

class UniModule(t.nn.Module):
    def __init__(self, hidden_size, num_heads):
        assert hidden_size % num_heads == 0
        super().__init__()
        self.hidden_size = hidden_size
        self.num_heads = num_heads
        self.head_size = hidden_size // num_heads

        self.attention = t.nn.Linear(hidden_size, hidden_size * 3)
        self.output_proj = t.nn.Linear(hidden_size, hidden_size)

    def forward(self, x): # b seq_len hidden_size
        qkv = self.attention(x)
        q, k, v = t.split(qkv, self.hidden_size, dim=-1)
        q = rearrange(q, 'b s (n h) -> b s n h', n=self.num_heads)
        k = rearrange(k, 'b s (n h) -> b s n h', n=self.num_heads)
        v = rearrange(v, 'b s (n h) -> b s n h', n=self.num_heads)
        qk = t.einsum('binl,bjnl->bnij', q, k)
        qk /= self.head_size**0.5
        qk = t.tril(qk)
        # setting everything qk can't attend to
        qk[t.triu(t.ones_like(qk), diagonal=1).bool()] = -1e4
        qk = F.softmax(qk, dim=-1)
        # qk: batch num_heads seq_len seq_len
        # v: batch seq_len num_heads head_size
        # out: batch num_heads seq_len head_size
        combined = t.einsum('bnij,bjnh->bnih', qk, v)
        combined = rearrange(combined, 'b n i h -> b i (n h)')
        return self.output_proj(combined)
# gpt_tests.test_unidirectional_attn(UniModule)

class GPT2Block(t.nn.Module):
    def __init__(self, hidden_size: int, num_heads: int, dropout: float, layer_norm_epsilon: float):
        super().__init__()
        self.layer_norm1 = t.nn.LayerNorm(normalized_shape=hidden_size, eps=layer_norm_epsilon)
        self.attention = UniModule(hidden_size, num_heads)
        self.layer_norm2 = t.nn.LayerNorm(normalized_shape=hidden_size, eps=layer_norm_epsilon)
        self.linear1 = t.nn.Linear(hidden_size, 4 * hidden_size)
        self.linear2 = t.nn.Linear(4 * hidden_size, hidden_size)
        self.dropout = t.nn.Dropout(dropout)

    def forward(self, x): # [batch, seq_len, hidden_size]
        layer_normed_1 = self.layer_norm1(x)
        attentioned = self.attention(layer_normed_1)
        attentioned_x = x + attentioned
        layer_normed_2 = self.layer_norm2(attentioned_x)
        mlped = self.dropout(self.linear2(F.gelu(self.linear1(layer_normed_2))))
        return attentioned_x + mlped
# gpt_tests.test_gpt_block(GPT2Block)

from dataclasses import dataclass
from torchtyping import TensorType

@dataclass
class GPT2Output:
    logits: TensorType["batch_size", "vocab_size"]
    final_encoding: TensorType["batch_size", "hidden_size"]
    # (final_encoding represents the encoding of the last word in the sequence.)

class GPT2Module(t.nn.Module):
    def __init__(self, num_layers, num_heads, vocab_size, hidden_size, max_position_embeddings, dropout, layer_norm_epsilon):
        super().__init__()
        self.embedding = t.nn.Parameter(t.randn(vocab_size, hidden_size))
        self.dropout = t.nn.Dropout(dropout)
        self.blocks = t.nn.ModuleList([
            GPT2Block(
                hidden_size, 
                num_heads, 
                dropout, 
                layer_norm_epsilon
            ) for _  in range(num_layers)
        ])
        self.layer_norm = t.nn.LayerNorm(normalized_shape=hidden_size, eps=layer_norm_epsilon)

    def forward(self, input_ids): # [batch, seq_len]  
        embedded_input = self.embedding[input_ids]
        return "some garbage"

# gpt_tests.test_gpt(GPT2Module)

m = t.arange(6).reshape(3, 2)
print(m)
inds = t.tensor([[0,0,0], [2,0,1]])
print(m, m[inds])
print(m.shape, inds.shape, m[inds].shape)
