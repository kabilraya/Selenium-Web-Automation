
import warnings
from contextlib import asynccontextmanager
import cv2
import numpy as np
import torch
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

warnings.filterwarnings("ignore", category=FutureWarning)

# Global variables for models
model = None
device = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Load models
    global model, whisper_model, device

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    print("Loading YOLO model...")
    model = torch.hub.load(
        "./yolo5", "custom", path="./yolo5/yolov5s.pt", source="local"
    )

    model.to(device)
    model.eval()

    if device.type == "cuda":
        model.half()

    # Warmup - run a dummy inference to initialize everything
    dummy_img = np.zeros((640, 640, 3), dtype=np.uint8)
    _ = model(dummy_img)

    print("YOLO model loaded and warmed up successfully!")
    yield

    # Shutdown: Clean up resources (if needed)
    print("Shutting down...")


app = FastAPI(title="YOLO Grid Detection API", lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "YOLO Grid Detection API is running"}


@app.post("/detect")
async def detect_grid(
    image: UploadFile = File(...),
    target_label: str = Form(...),
    grid_rows: int = Form(3),
    grid_cols: int = Form(3),
    conf_threshold: float = Form(0.25),  # Confidence threshold
    img_size: int = Form(640),  # Inference size (smaller = faster)
):
    """
    Detect objects in a grid image and return indexes containing the target label.

    Args:
        image: Image file (JPEG, PNG)
        target_label: Class label to filter (e.g., "car", "bus", "person")
        grid_rows: Number of rows in grid (default: 3)
        grid_cols: Number of columns in grid (default: 3)
        conf_threshold: Confidence threshold for detections (default: 0.25)
        img_size: Input image size for inference - smaller is faster (default: 640)

    Returns:
        JSON with grid indexes containing the target label
    """
    try:
        # Read image bytes
        contents = await image.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return JSONResponse(
                status_code=400, content={"error": "Invalid image file"}
            )

        img_height, img_width = img.shape[:2]

        # Run inference with optimizations
        with torch.no_grad():  # Disable gradient computation
            results = model(img, size=img_size)  # Use specified size

        # Calculate grid cell dimensions
        cell_height = img_height / grid_rows
        cell_width = img_width / grid_cols

        # Parse results
        detections = results.pandas().xyxy[0]

        # Filter by target label AND confidence threshold
        filtered = detections[
            (detections["name"] == target_label)
            & (detections["confidence"] >= conf_threshold)
        ]

        # Determine which grid cells contain the target
        grid_indexes = set()
        detection_details = []

        for idx, row in filtered.iterrows():
            # Get bounding box coordinates
            xmin, ymin = row["xmin"], row["ymin"]
            xmax, ymax = row["xmax"], row["ymax"]
            center_x = (xmin + xmax) / 2
            center_y = (ymin + ymax) / 2

            # Calculate center cell position
            center_col_idx = int(center_x / cell_width)
            center_row_idx = int(center_y / cell_height)

            # Find all grid cells that overlap with this bounding box
            # Calculate which cells the bbox spans
            col_start = int(xmin / cell_width)
            col_end = int(xmax / cell_width)
            row_start = int(ymin / cell_height)
            row_end = int(ymax / cell_height)

            # Clamp to grid boundaries
            col_start = max(0, min(col_start, grid_cols - 1))
            col_end = max(0, min(col_end, grid_cols - 1))
            row_start = max(0, min(row_start, grid_rows - 1))
            row_end = max(0, min(row_end, grid_rows - 1))

            # Add all overlapping cells
            overlapping_cells = []
            for r in range(row_start, row_end + 1):
                for c in range(col_start, col_end + 1):
                    grid_index = r * grid_cols + c
                    grid_indexes.add(grid_index)
                    overlapping_cells.append(grid_index)

            detection_details.append(
                {
                    "grid_indexes": overlapping_cells,
                    "grid_position": {"row": center_row_idx, "col": center_col_idx},
                    "confidence": round(float(row["confidence"]), 3),
                    "bbox": {
                        "x1": int(xmin),
                        "y1": int(ymin),
                        "x2": int(xmax),
                        "y2": int(ymax),
                    },
                    "center": {"x": int(center_x), "y": int(center_y)},
                    "spans_cells": {
                        "rows": f"{row_start}-{row_end}",
                        "cols": f"{col_start}-{col_end}",
                    },
                }
            )

        return {
            "success": True,
            "target_label": target_label,
            "grid_size": {"rows": grid_rows, "cols": grid_cols},
            "grid_indexes": sorted(list(grid_indexes)),
            "total_detections": len(detection_details),
            "detections": detection_details,
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "yolo_model_loaded": model is not None,
        "whisper_model_loaded": whisper_model is not None,
        "device": str(device),
    }
