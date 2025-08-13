import cv2

def capture_image(resolution=(1260, 720)):
    """
    调用摄像头拍照并保存到当前文件夹的 captured_image.jpg 文件中
    :param resolution: 设置分辨率，格式为 (width, height)，例如 (1280, 720)
    :return: 照片的路径
    """
    cap = cv2.VideoCapture(0,cv2.CAP_V4L2)  # 移除了CAP_DSHOW
    if not cap.isOpened():
        raise Exception("无法打开摄像头")

    # 设置分辨率
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])

    ret, frame = cap.read()
    if not ret:
        raise Exception("无法读取摄像头画面")

    # 保存照片到当前文件夹
    image_path = "captured_image.jpg"
    cv2.imwrite(image_path, frame)
    cap.release()
    return image_path

def capture_image_async():
    """异步调用摄像头拍照"""
    try:
        capture_image()
    except Exception as e:
        print(f"拍照时发生错误: {str(e)}")


if __name__ == "__main__":  # 修正了这里的条件
    capture_image()