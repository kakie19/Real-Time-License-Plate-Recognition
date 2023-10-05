import cv2
import numpy as np
from ultralytics import YOLO
import easyocr
from util import write_csv, char2int, int2char
import os, uuid



# Initialize necessary variables and models
lp_folder_path = "./licenses_plates_imgs_detected/"
vehicle_folder_path = "./vehicles/"
LICENSE_MODEL_DETECTION_DIR = './models/license_plate_detector.pt'
COCO_MODEL_DIR = "./models/yolov8s.pt"

reader = easyocr.Reader(['en'], gpu=True)
vehicles = {2: "Car", 3: "Motorcycle", 5: "Bus", 6: "Truck"}

coco_model = YOLO(COCO_MODEL_DIR)
license_plate_detector = YOLO(LICENSE_MODEL_DETECTION_DIR)

threshold = 0.15

class VideoProcessor:
    def recv(self, img):
        return img

def read_license_plate(license_plate_crop, img):
    scores = 0
    detections = reader.readtext(license_plate_crop)

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

def model_prediction(img, frame_number):
    license_numbers = 0
    results = {}
    licenses_texts = []

    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    object_detections = coco_model.track(img, persist=True)[0]
    vehicle_detected = False
    vehicle_bboxes = []

    if len(object_detections.boxes.cls.tolist()) != 0:
        for detection in object_detections.boxes.data.tolist():
            if len(detection) == 7:
                xvehicle1, yvehicle1, xvehicle2, yvehicle2, track_id, vehicle_score, class_id = detection

                if int(class_id) in vehicles:
                    class_name = vehicles[int(class_id)]
                    label = f"{class_name}-{int(track_id)}"
                    cv2.rectangle(img, (int(xvehicle1), int(yvehicle1)), (int(xvehicle2), int(yvehicle2)), (0, 0, 255), 3)
                    cv2.putText(img, label, (int(xvehicle1), int(yvehicle1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                    vehicle_detected = True
                    vehicle_bboxes.append([xvehicle1, yvehicle1, xvehicle2, yvehicle2, vehicle_score, class_name])  # store class name instead of class id

        if vehicle_detected:
            license_detections = license_plate_detector.track(img, persist=True)[0]
            
            if len(license_detections.boxes.cls.tolist()) != 0:
                license_plate_crops_total = []
                for license_plate in license_detections.boxes.data.tolist():
                    if len(license_plate) == 7:
                        x1, y1, x2, y2, score, _, class_name = license_plate

                        # Check if this license plate is inside any vehicle bounding box
                        for veh_bbox in vehicle_bboxes:
                            xvehicle1, yvehicle1, xvehicle2, yvehicle2, vehicle_score, veh_class_id = veh_bbox
                            
                            if x1 > xvehicle1 and x2 < xvehicle2 and y1 > yvehicle1 and y2 < yvehicle2:
                                # This license plate is inside this vehicle bounding box
                                cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 3)

                                
                                license_plate_crop = img[int(y1):int(y2), int(x1): int(x2), :]
                                img_name = '{}.jpg'.format(uuid.uuid1())
                                cv2.imwrite(os.path.join(lp_folder_path, img_name), license_plate_crop)

                                license_plate_crop_gray = cv2.cvtColor(license_plate_crop, cv2.COLOR_BGR2GRAY)
                                license_plate_crop_gray = cv2.equalizeHist(license_plate_crop_gray)
                                license_plate_crop_gray = cv2.medianBlur(license_plate_crop_gray, 3)
                                
                                cv2.imshow('Grayscale Image', license_plate_crop_gray)
                                license_plate_text, license_plate_text_score = read_license_plate(license_plate_crop_gray, img)

                                licenses_texts.append(license_plate_text)

                                if license_plate_text is not None and license_plate_text_score is not None:
                                    if license_plate_text_score >= 0.3:
                                        lp_length = len(license_plate_text)

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

                                            elif lp_length == 7:
                                                l = license_plate_text[:2]
                                                n = license_plate_text[2:lp_length]
                                                # Check if 'l' contains a number
                                                if any(char.isdigit() for char in l):
                                                    l = int2char(l)
                                                # Check if 'n' contains a letter
                                                if any(char.isalpha() for char in n):
                                                    n = char2int(n)
                                                license_plate_text = (l + "-" + n)


                                        # Drawing the recognized license plate number on the image
                                        cv2.rectangle(img, (int(x1), int(y1) - 40), (int(x2)+10, int(y1)), (169, 169, 169), cv2.FILLED)
                                        cv2.putText(img, str(license_plate_text), (int(x1), int(y1) - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

                                        # Adding class name and score to the preview
                                        cv2.putText(img, f"Class: {veh_class_id}, Score: {round(vehicle_score, 2)}", (int(x1), int(y1) - 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                                        
                                        # Adding license number score to the preview
                                        cv2.putText(img, f"LP Score: {round(license_plate_text_score, 2)}", (int(x1), int(y1) - 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                                        license_plate_crops_total.append(license_plate_crop)
                                        
                                        # Save a cropped image of the car
                                        car_crop = img[int(yvehicle1):int(yvehicle2), int(xvehicle1):int(xvehicle2), :]
                                        car_img_name = f'{veh_class_id}{frame_number}_{license_numbers}.jpg'
                                        cv2.imwrite(os.path.join(vehicle_folder_path, car_img_name), car_crop)

                                        results[license_numbers] = {
                                                                    license_numbers: {
                                                                        'car': {
                                                                            'bbox': [xvehicle1, yvehicle1, xvehicle2, yvehicle2], 
                                                                            'vehicle_score': vehicle_score,
                                                                            'vehicle_img': car_img_name,  # Add the path to the vehicle image
                                                                            'vehicle_class': veh_class_id  # Add the vehicle class
                                                                        },
                                                                        'license_plate': {
                                                                            'bbox': [x1, y1, x2, y2], 
                                                                            'text': license_plate_text, 
                                                                            'bbox_score': score, 
                                                                            'text_score': license_plate_text_score
                                                                        }
                                                                    }
                                                                }
                                    license_numbers += 1
                                    write_csv(results, f"./results/detection_results.csv")
              
                img_wth_box = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                return [img_wth_box, licenses_texts, license_plate_crops_total, results]
    else:
        xvehicle1, yvehicle1, xvehicle2, yvehicle2 = 0, 0, 0, 0
        vehicle_score = 0

    img_wth_box = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return [img_wth_box, [], [], {}]  # Include an empty dictionary for results



def main():
    cap = cv2.VideoCapture(0)
    processor = VideoProcessor()
    frame_number = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Process the frame
        processed_frame = processor.recv(frame)
        result = model_prediction(processed_frame, frame_number)
        processed_frame = result[0]

        # Increment frame number
        frame_number += 1

        # Display the processed frame
        # Set the desired width and height for the resized frames
        width = 1280
        height = 720
        processed_frame = cv2.resize(processed_frame, (width, height))
        cv2.imshow("Tech Titans Realtime License Plate Recognition", processed_frame)

        # Break the loop on pressing 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Release the video capture object and close OpenCV windows
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
