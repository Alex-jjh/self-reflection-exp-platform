"""Experiment runtime: cells, blinding, resumable atomic storage, adaptive
concurrency, credential pause/resume, status.

This package does not know where AI credentials come from or which provider
answers. It never imports boto3, botocore or ``bedrock_access``; it drives any
object that satisfies the backend contract in ``contract.py``.
"""
