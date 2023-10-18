from skimage import io
import numpy as np
from tifffile import imsave
import cv2
import matplotlib.pyplot as plt


def crop_video_rect(
        video_path: str,
        top_left: tuple,
        bottom_right: tuple,
        save_path: str = None):
    full_img_stack = io.imread(video_path)

    # plt.imshow(full_img_stack[len(full_img_stack)-1], cmap=plt.cm.gray)

    new_image_size = (full_img_stack.shape[0], bottom_right[0] - top_left[0] + 1, bottom_right[1] - top_left[1] + 1)
    template = np.zeros(new_image_size, np.uint16)

    bottom_right = (bottom_right[0] + 1, bottom_right[1] + 1)

    for img_idx in range(len(full_img_stack)):
        img = full_img_stack[img_idx]
        partial_img = img[top_left[0]:bottom_right[0], top_left[1]:bottom_right[1]]

        template[img_idx] = partial_img
    imsave(save_path, template)
    # imsave(
    #     "C:\\Users\\Sarit Hollander\\Desktop\\Study\\MSc\\Research\\Project\\Intracellular_Information_Processing\\Data\\Pillars\\5.3\\exp-20230809-video-00-cell-1-Airyscan Processing.tif",
    #     template)


# crop_video_rect(
#     'C:\\Users\\Sarit Hollander\\Desktop\\Study\\MSc\\Research\\Project\\Intracellular_Information_Processing\\Data\\Pillars\\5.3\\20230809-video-00-Airyscan Processing.tif',
#     (91, 172), (132, 214),
#     # (101, 282), (144, 327)
#     # (214, 321), (255, 353)
#     # (322, 57), (357, 99)
#     # (230, 50), (298, 126)
# )


# 'C:\\Users\\Sarit Hollander\\Desktop\\Study\\MSc\\Research\\Project\\Intracellular_Information_Processing\\Data\\Pillars\\5.3\\exp-2023071301-video-01-cell-6-Airyscan Processing.tif',
# (30,270),	(205,460)
# (530, 105),	(755,366)
# (815,170),	(1088,480)
# (835,1530),	(1040,1766)
# (1185,995),	(1438,1276)
# (1460,1015),	(1662,1270)
# (1345,1395),	(1555,1628)
# (1672,1918),	(1925,2195)
# )


def crop_video_circle(
        video_path: str,
        circle_center: tuple,
        radius: int):
    full_img_stack = io.imread(video_path)

    new_image_size = (full_img_stack.shape[0], radius * 2 + 1, radius * 2 + 1)

    img_height = full_img_stack.shape[1]
    img_width = full_img_stack.shape[2]

    template = np.zeros(new_image_size, np.uint16)

    template_height = template.shape[1]
    template_width = template.shape[2]

    mask = np.ones((template_height, template_width), np.uint8)
    mask += 255
    color = 1
    thickness = -1

    cv2.circle(mask, (template_height // 2, template_width // 2), radius, color, thickness)
    for img_idx in range(len(full_img_stack)):
        img = full_img_stack[img_idx]

        img = img[circle_center[0] - radius:circle_center[0] + radius + 1,
              circle_center[1] - radius:circle_center[1] + radius + 1]

        masked_img = np.where(mask, img, 0)
        template[img_idx] = masked_img

    imsave(
        "C:\\Users\\Sarit Hollander\\Desktop\\Study\\MSc\\Research\\Project\\Intracellular_Information_Processing\\Data\\Pillars\\5.3\\exp-2023081501-video-01-cell-7-Airyscan Processing3.tif",
        template)


def crop_video_triangle(
        video_path: str,
        p1,
        p2,
        p3):
    full_img_stack = io.imread(video_path)
    # template = np.zeros(full_img_stack.shape, np.uint16)
    # (200, 200) is in
    mask = np.ones((full_img_stack.shape[1], full_img_stack.shape[2]), np.uint8)

    for row in range(full_img_stack.shape[1] + 1):
        for col in range(full_img_stack.shape[2] + 1):
            if isInside(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1], row, col):
                mask[row][col] = 0

    for img_idx in range(len(full_img_stack)):
        img = full_img_stack[img_idx]

        masked_img = np.where(mask, img, 0)
        full_img_stack[img_idx] = masked_img

    imsave(
        "C:\\Users\\Sarit Hollander\\Desktop\\Study\\MSc\\Research\\Project\\Intracellular_Information_Processing\\Data\\Pillars\\5.3\\exp-20230809-video-03-cell-5-Airyscan Processing2.tif",
        full_img_stack)


def area(x1, y1, x2, y2, x3, y3):
    return abs((x1 * (y2 - y3) + x2 * (y3 - y1)
                + x3 * (y1 - y2)) / 2.0)


# A function to check whether point P(x, y)
# lies inside the triangle formed by
# A(x1, y1), B(x2, y2) and C(x3, y3)
def isInside(x1, y1, x2, y2, x3, y3, x, y):
    # Calculate area of triangle ABC
    A = area(x1, y1, x2, y2, x3, y3)

    # Calculate area of triangle PBC
    A1 = area(x, y, x2, y2, x3, y3)

    # Calculate area of triangle PAC
    A2 = area(x1, y1, x, y, x3, y3)

    # Calculate area of triangle PAB
    A3 = area(x1, y1, x2, y2, x, y)

    # Check if sum of A1, A2 and A3
    # is same as A
    if (A == A1 + A2 + A3):
        return True
    else:
        return False


def skip_frame(
        video_path: str,
        frames_to_discard: list):
    full_img_stack = io.imread(video_path)

    # plt.imshow(full_img_stack[len(full_img_stack)-1], cmap=plt.cm.gray)

    frames_to_discard = list(np.array(frames_to_discard) - 1)

    # Create a new list to store the filtered images
    filtered_images = []

    # Iterate through the image stack
    for idx, image in enumerate(full_img_stack):
        if idx not in frames_to_discard:
            filtered_images.append(image)

    # Convert the filtered images list back to an array
    filtered_image_stack = np.array(filtered_images)

    # Optional: Save the filtered image stack
    io.imsave(
        "C:\\Users\\Sarit Hollander\\Desktop\\Study\\MSc\\Research\\Project\\Intracellular_Information_Processing\\Data\\Pillars\\5.3\\20230818-video-03-Airyscan Processing_skiped_noise.tif",
        filtered_image_stack)

# skip_frame(video_path="C:\\Users\\Sarit Hollander\\Desktop\\Study\\MSc\\Research\\Project\\Intracellular_Information_Processing\\Data\\Pillars\\5.3\\20230818-video-03-Airyscan Processing.tif",
#            frames_to_discard=[35])

# crop_video_triangle(
#     "C:\\Users\\Sarit Hollander\\Desktop\\Study\\MSc\\Research\\Project\\Intracellular_Information_Processing\\Data\\Pillars\\5.3\\exp-20230809-video-03-cell-5-Airyscan Processing.tif",
# (160,0),
# (324,130),
# (324,0)
# )
# (140, 242),
# (225, 242),
# (225, 116)
# (-0.5, -0.5),
# (-0.5, 180),
# (128, -0.5)
# )

# crop_video_circle(
#     'C:\\Users\\Sarit Hollander\\Desktop\\Study\\MSc\\Research\\Project\\Intracellular_Information_Processing\\Data\\Pillars\\5.3\\exp-20230809-video-04-cell-3-Airyscan Processing2.tif',
#     (280, 206),
#     30)
