"""SkyTrace processing pipeline.

Sub-packages correspond to independent pipeline stages (video ingestion,
reconstruction, georeferencing, object detection, measurement, confidence).
Each stage is designed to communicate with the next via simple, file-based
contracts rather than shared in-process objects.
"""
