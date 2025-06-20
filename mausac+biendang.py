import cv2
import numpy as np
from tkinter import Tk, filedialog
import socket
import time

# 1. Chọn ảnh
def select_image():
    root = Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title="Chọn ảnh")
    root.destroy()
    return file_path

# 2. Đếm số lượng vật thể trên ảnh (theo mask đỏ/xanh dương) và phân biệt hình vuông/chữ nhật
def count_objects(image_path, debug=False):
    image = cv2.imread(image_path)
    if image is None:
        print("Không đọc được ảnh!")
        return 0, [], (0, 0)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([180, 255, 255])
    lower_blue = np.array([100, 100, 100])
    upper_blue = np.array([130, 255, 255])

    mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)
    mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)

    if debug:
        cv2.imshow("Red mask", mask_red)
        cv2.imshow("Blue mask", mask_blue)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    objects = []
    for color, mask in [("red", mask_red), ("blue", mask_blue)]:
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 100:  # Tùy chỉnh theo kích thước vật thể thực tế
                M = cv2.moments(cnt)
                if M['m00'] != 0:
                    cx = int(M['m10']/M['m00'])
                    cy = int(M['m01']/M['m00'])

                    # Lấy bounding rect để tính tỉ lệ khung bao contour
                    x, y, w, h = cv2.boundingRect(cnt)
                    aspect_ratio = float(w) / h
                    # Xác định hình vuông hay hình chữ nhật
                    if 0.9 <= aspect_ratio <= 1.1:
                        shape = "square"
                    else:
                        shape = "rectangle"

                    objects.append({
                        "color": color,
                        "pixel": (cx, cy),
                        "area": area,
                        "shape": shape
                    })
    return len(objects), objects, image.shape

# 3. Kết nối robot MG400
class DobotClient:
    def __init__(self, ip="192.168.1.6"):
        self.dash_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dash_sock.connect((ip, 29999))
        self.motion_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.motion_sock.connect((ip, 30003))

    def send_dashboard(self, cmd):
        self.dash_sock.sendall((cmd + '\n').encode())
        return self.dash_sock.recv(1024).decode()

    def send_motion(self, cmd):
        self.motion_sock.sendall((cmd + '\n').encode())
        return self.motion_sock.recv(1024).decode()

    def enable_robot(self):
        return self.send_dashboard("EnableRobot()")

    def clear_error(self):
        return self.send_dashboard("ClearError()")

    def movl(self, x, y, z, r):
        return self.send_motion(f"MovL({x},{y},{z},{r})")

    def close(self):
        self.dash_sock.close()
        self.motion_sock.close()

# 4. Hàm chuyển đổi pixel sang tọa độ robot (cần calibrate thực tế!)
def pixel_to_robot(pixel, image_shape):
    px, py = pixel
    img_h, img_w = image_shape[:2]
    # Ví dụ giả lập: vùng ảnh là 640x480, vùng robot thao tác X=200-400mm, Y=-200->0mm
    X = 438.8944 + (px / 2592)* (336.722 - 438.8944) 
    Y = -360.4887 + (py / 1944) * (1935.0909 + 360.4887)  
    Z = -100
    R = 0

    return (X, Y, Z, R)

# 5. Main
def main():
    image_path = select_image()
    if not image_path:
        print("Không chọn ảnh nào.")
        return

    print("Đang đếm số lượng vật thể ...")
    num_obj, objects, image_shape = count_objects(image_path, debug=False)
    print(f"Số lượng vật thể phát hiện được: {num_obj}")

    if num_obj == 0:
        print("Không tìm thấy vật thể phù hợp trên ảnh!")
        return

    for i, obj in enumerate(objects):
        print(f"#{i+1}: {obj['color']} tại pixel {obj['pixel']} diện tích {obj['area']:.1f} hình {obj['shape']}")

    robot = DobotClient(ip="192.168.1.6")
    print("Enable robot:", robot.enable_robot())
    time.sleep(0.5)
    print("Clear error:", robot.clear_error())
    time.sleep(0.2)

    for idx, obj in enumerate(objects):
        x, y, z, r = pixel_to_robot(obj['pixel'], image_shape)
        print(f"({idx+1}) Robot đi đến {obj['color']} tại ({x:.1f}, {y:.1f}, {z:.1f}, {r:.1f})")
        result = robot.movl(x, y, z, r)
        print("Kết quả MovL:", result)
        # Nếu có tích hợp IO hút/gắp, bổ sung lệnh điều khiển tại đây
        time.sleep(0.5)

    robot.close()
    print("Hoàn thành nhặt tất cả vật thể.")

if __name__ == "__main__":
    main()
