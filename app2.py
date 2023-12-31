import cv2
import numpy as np
from ultralytics import YOLO
import easyocr
from util import write_csv, char2int, int2char
import os, re, sys
import matplotlib.pyplot as plt


lp_folder_path = "./licenses_plates_imgs_detected/"
vehicle_folder_path = "./vehicles/"
model = YOLO("./models/yolov8n.pt")
license_plate_detector = YOLO('./models/license_plate_detector.pt')
vehicles = {2: "Car", 3: "Motorcycle", 5: "Bus", 6: "Truck"}
reader = easyocr.Reader(['en'], gpu=True)


def read_license_plate(license_plate_crop, img):
    scores = 0
    detections = reader.readtext(license_plate_crop, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')

    width = img.shape[1]
    height = img.shape[0]
    
    if detections == [] :
        return None, None

    rectangle_size = license_plate_crop.shape[0]*license_plate_crop.shape[1]

    plate = [] 

    for result in detections:
        length = np.sum(np.subtract(result[0][1], result[0][0]))
        height = np.sum(np.subtract(result[0][2], result[0][1]))
        
        if length*height / rectangle_size > 0.17:
            bbox, text, score = result
            text = result[1]
            text = text.upper()
            scores += score
            plate.append(text)
    
    if len(plate) != 0 : 
        return " ".join(plate), scores/len(plate)
    else :
        return " ".join(plate), 0
    

def model_predection(frame):
    # Run YOLOv8 tracking on the frame, persisting tracks between frames
    vehicle_detection = model.track(frame, persist=True)[0]
    vehicle_detected = False
    vehicle_bboxes = []
    lp_bbox = []
    license_numbers = 0
    licenses_texts = []
    results = {}


    if len(vehicle_detection.boxes.cls.tolist()) != 0:
        for detection in vehicle_detection.boxes.data.tolist():
            # Extracting bounding box coordinates, track_id , detection_score, class_id from the detection
            if len(detection) == 7:
                xvehicle1, yvehicle1, xvehicle2, yvehicle2, track_id, vehicle_score, class_id = detection

                #If the detected class_id is in Vehicle Dictionary , draw rectangle around it.
                if int(class_id) in vehicles:
                    class_name = vehicles[int(class_id)]
                    label = f"{class_name}-{int(track_id)}"
                    cv2.rectangle(frame, (int(xvehicle1), int(yvehicle1)), (int(xvehicle2), int(yvehicle2)), (0, 0, 255), 3)
                    cv2.putText(frame, label, (int(xvehicle1), int(yvehicle1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    vehicle_detected = True
                    # Storing bounding box details with vehicle class name instead of class ID
                    vehicle_bboxes.append([track_id, xvehicle1, yvehicle1, xvehicle2, yvehicle2, vehicle_score, class_name])  # store class name instead of class id

        #If Vehicle is detected detect license plate
        if vehicle_detected:
            license_detections = license_plate_detector.track(frame, persist=True)[0]
            
            #If license plate is detected 
            if len(license_detections.boxes.cls.tolist()) != 0:
                #Storing all license plate crops
                license_plate_crops_total = []
                for license_plate in license_detections.boxes.data.tolist():
                    if len(license_plate) == 7:
                        #Bounding box coordinates and other details of license plate
                        xplate1, yplate1, xplate2, yplate2, lp_track_id, lp_score, class_id = license_plate

                        # Check if license plate is inside vehicle bounding box
                        for veh_bbox in vehicle_bboxes:
                            #Get Bbox of the vehicle
                            xvehicle1, yvehicle1, xvehicle2, yvehicle2, track_id2, vehicle_score, class_name = veh_bbox
                            
                            #Check if license plate bbox is within the bbox of the vehicle
                            if xplate1 > xvehicle1 and xplate2 > xvehicle2 and yplate1 < yvehicle1 and yplate2 < yvehicle2:
                                cv2.rectangle(frame, (int(xplate1), int(yplate1)), (int(xplate2), int(yplate2)), (0, 255, 0), 3)
                                lp_bbox.append([xplate1, yplate1, xplate2, yplate2, lp_track_id, lp_score])
                                
                                #Cropping the license plate frame if it meets the threshold
                                if lp_score >= 0.1:
                                    license_plate_crop = frame[int(yplate1):int(yplate2), int(xplate1): int(xplate2), :]                                
                                    #Convert to grayscale and get the LP text and score
                                    license_plate_crop_gray = cv2.cvtColor(license_plate_crop, cv2.COLOR_BGR2GRAY) 
                                    license_plate_crop_gray = cv2.equalizeHist(license_plate_crop_gray)
                                    license_plate_crop_gray = cv2.medianBlur(license_plate_crop_gray, 3)
                                    _, license_plate_crop_gray = cv2.threshold(license_plate_crop_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                                    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                                    license_plate_crop_gray = cv2.morphologyEx(license_plate_crop_gray, cv2.MORPH_CLOSE, kernel)

                                    #Apply OCR
                                    license_plate_text, license_plate_text_score = read_license_plate(license_plate_crop_gray, frame)

                                    #Processing the recognized text to remove unwanted characters
                                    if license_plate_text is not None:
                                        lp_length = len(license_plate_text)

                                        #Formatting the license plate text based on the vehicle type
                                        if class_name in ["Car", "Bus", "Truck"]:
                                            if lp_length >= 6:
                                                l = license_plate_text[:3]
                                                n = license_plate_text[3:lp_length]
                                                # Check if 'l' contains a number
                                                if any(char.isdigit() for char in l):
                                                    l = int2char(l)
                                                # Check if 'n' contains a letter
                                                if any(char.isalpha() for char in n):
                                                    n = char2int(n)
                                                license_plate_text = (l + "-" + n)

                                        elif class_name == "Motorcycle":
                                            if lp_length == 6:
                                                n = license_plate_text[:3]
                                                l = license_plate_text[3:6]
                                                # Check if 'l' contains a number
                                                if any(char.isdigit() for char in l):
                                                    l = int2char(l)
                                                # Check if 'n' contains a letter
                                                if any(char.isalpha() for char in n):
                                                    n = char2int(n)
                                                license_plate_text = (n + "-" + l)

                                            elif lp_length > 6 and lp_length < 7:
                                                l = license_plate_text[:2]
                                                n = license_plate_text[2:lp_length]
                                                # Check if 'l' contains a number
                                                if any(char.isdigit() for char in l):
                                                    l = int2char(l)
                                                # Check if 'n' contains a letter
                                                if any(char.isalpha() for char in n):
                                                    n = char2int(n)
                                                license_plate_text = (l + "-" + n)

                                        #Handling cases where license plate text is unreadable or not recognized properly
                                        elif license_plate_text_score <= 0.2:
                                            license_plate_text = "Unreadable License Plate"

                                        # Check if the formatted text is valid, if not set a default value
                                        # else:
                                        #     license_plate_text = "License plate not recognized"                    

                                        lp_label = f"License Plate: {license_plate_text}"
                                        cv2.rectangle(frame, (int(xplate1), int(yplate1) - 40), (int(xplate2), int(yplate1)), (255, 255, 255), cv2.FILLED)
                                        cv2.putText(frame, lp_label, (int(xplate1), int(yplate1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0))
                                        license_plate_crops_total.append(license_plate_crop)
                                        
                                        # Save a cropped image of the car and license plate
                                        img_name = f"{int(lp_track_id)}_{license_plate_text}"
                                        cv2.imwrite(os.path.join(lp_folder_path, img_name), license_plate_crop)
                                        car_crop = frame[int(yvehicle1):int(yvehicle2), int(xvehicle1):int(xvehicle2), :]
                                        car_img_name = f'{class_name}{track_id2}_{license_numbers}.jpg'
                                        cv2.imwrite(os.path.join(vehicle_folder_path, car_img_name), car_crop)
                                        results[track_id] = {
                                                                'vehicle_details': {
                                                                    'track_id': int(track_id),
                                                                    'class_name': class_name,
                                                                    'car_img_name': car_img_name,  # Ensure you capture the car image name correctly
                                                                },
                                                                'license_plate_details': {
                                                                    'lp_track_id': int(lp_track_id),
                                                                    'img_name': img_name,  # Ensure you capture the license plate image name correctly
                                                                    'license_plate_text': license_plate_text,  # Ensure you extract the license plate text correctly
                                                                    'lp_score': lp_score,  # Ensure you capture the license plate score correctly
                                                                }
                                                            }  
                                    license_numbers += 1
                                    write_csv(results, f"./results/detection_results.csv")
    return frame

cap = cv2.VideoCapture(2)

# Set the desired width and height for the resized frames
width = 640
height = 480

ret = True
while cap.isOpened():
    # Read a frame from the video
    success, frame = cap.read()
    frame = cv2.resize(frame, (width, height))
    if success:
        model_predection(frame)
        # Display the annotated frame
        cv2.imshow("Tech Titans Realtime License Plate Recognition", frame)

        # Break the loop if 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break
    else:
        # Break the loop if the end of the video is reached
        break

# Release the video capture object and close the display window
cap.release()
cv2.destroyAllWindows()
