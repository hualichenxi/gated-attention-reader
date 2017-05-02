#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function

import torch
import torch.nn.functional as F


def torchconcat(t1, t2):
    return torch.concat([t1, t2], axis=2)


def torchsum(t1, t2):
    return t1 + t2


def gated_attention(doc, qry, inter, mask, gating_fn='torch.mul'):
    # doc: B x N x D
    # qry: B x Q x D
    # inter: B x N x Q
    # mask (qry): B x Q
    alphas_r = F.softmax(inter) * mask[:, None, :].float().expand_as(inter)
    alphas_r = alphas_r / \
        torch.sum(alphas_r, dim=2).expand_as(alphas_r)  # B x N x Q
    q_rep = torch.bmm(alphas_r, qry)  # B x N x D
    return eval(gating_fn)(doc, q_rep)


def pairwise_interaction(doc, qry):
    # doc: B x N x D
    # qry: B x Q x D
    shuffled = qry.permute(0, 2, 1)  # B x D x Q
    return torch.bmm(doc, shuffled)  # B x N x Q


def attention_sum(doc, qry, cand, cloze, cand_mask):
    # doc: B x N x D
    # qry: B x Q x D
    # cand: B x N x C
    # cloze: B x 1
    # cand_mask: B x N
    # TODO: advanced indexing
    for i in range(qry.size(0)):
        cloze[i] = cloze[i] + qry.size(1) * i
    q = torch.index_select(
        qry.contiguous().view([-1, qry.size(-1)]), 0, cloze.long())  # B x D
    p = torch.squeeze(
        torch.bmm(doc, q.unsqueeze(dim=-1)), dim=-1)  # B x N
    pm = F.softmax(p) * cand_mask.float()  # B x N
    pm = pm / torch.sum(pm, dim=1).expand_as(pm)  # B x N
    pm = pm.unsqueeze(1)  # B x 1 x N
    return torch.squeeze(
        torch.bmm(pm, cand.float()), dim=1)  # B x C


def gru(inputs, mask, cell):
    """
    Args:
    inputs: batch_size x seq_len x n_feat
    mask: batch_size x seq_len
    cell: GRU/LSTM/RNN
    """
    seq_lengths = torch.sum(mask, dim=-1).squeeze(-1)
    sorted_len, sorted_idx = seq_lengths.sort(0, descending=True)
    index_sorted_idx = sorted_idx\
        .view(-1, 1, 1).expand_as(inputs)
    sorted_inputs = inputs.gather(0, index_sorted_idx.long())
    packed_seq = torch.nn.utils.rnn.pack_padded_sequence(
        sorted_inputs, sorted_len.data.numpy(), batch_first=True)
    out, _ = cell(packed_seq)
    unpacked, unpacked_len = \
        torch.nn.utils.rnn.pad_packed_sequence(
            out, batch_first=True)
    _, original_idx = sorted_idx.sort(0, descending=True)
    unsorted_idx = original_idx\
        .view(-1, 1, 1).expand_as(unpacked)
    output_seq = unpacked.gather(0, unsorted_idx.long())
    return output_seq, seq_lengths
