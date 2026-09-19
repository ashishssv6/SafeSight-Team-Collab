from ultralytics import YOLO

# Load a pretrained YOLO model
model = YOLO("yolov8n.pt")

# Run YOLO on the webcam
model.predict(source=0, show=True)