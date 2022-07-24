from Pillars.pillars_utils import *
from Pillars.consts import *
import cv2


def create_mask_of_circles(radius: int, centers: list):
    """
    Creating mask of circles according to the centers of the pillars in the image
    :param radius: the pillar's radius
    :param centers: the centers of each pillar in the image
    :return: mask - ndarray in the size of the input image
    """
    mask = np.zeros((Consts.IMAGE_SIZE, Consts.IMAGE_SIZE), np.uint8)
    mask += 255
    color = 0
    thickness = -1

    for center in centers:
        cv2.circle(mask, (center[1], center[0]), radius, color, thickness)

    cv2.imshow("mask", mask)
    cv2.waitKey(0)
    return mask


def get_mask_for_each_pillar():
    """
    Mapping each pillar to its fitting mask
    :return:
    """

    if Consts.USE_CACHE and os.path.isfile(Consts.mask_for_each_pillar_cache_path):
        with open(Consts.mask_for_each_pillar_cache_path, 'rb') as handle:
            pillar_to_neighbors = pickle.load(handle)
            return pillar_to_neighbors

    centers = find_centers_with_logic()
    thickness = -1
    pillar_to_mask_dict = {}
    for center in centers:
        small_mask_template = np.zeros((Consts.IMAGE_SIZE, Consts.IMAGE_SIZE), np.uint8)
        cv2.circle(small_mask_template, (center[1], center[0]), Consts.SMALL_MASK_RADIUS, 255, thickness)

        large_mask_template = np.zeros((Consts.IMAGE_SIZE, Consts.IMAGE_SIZE), np.uint8)
        cv2.circle(large_mask_template, (center[1], center[0]), Consts.LARGE_MASK_RADIUS, 255, thickness)

        mask = large_mask_template - small_mask_template

        pillar_to_mask_dict[center] = mask

    if Consts.USE_CACHE:
        with open(Consts.mask_for_each_pillar_cache_path, 'wb') as handle:
            pickle.dump(pillar_to_mask_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)

    return pillar_to_mask_dict


def build_pillars_mask():
    """
    Building the mask to the image by substitute 2 masks of circles with different radius to create the full image mask
    :param masks_path:
    :param logic_centers:
    :return:
    """
    centers = find_centers_with_logic()
    small_mask = create_mask_of_circles(Consts.SMALL_MASK_RADIUS, centers)
    large_mask = create_mask_of_circles(Consts.LARGE_MASK_RADIUS, centers)
    pillars_mask = large_mask - small_mask
    pillars_mask *= 255

    cv2.imshow('pillars_mask', pillars_mask)
    # with open(masks_path, 'wb') as f:
    #     np.save(f, pillars_mask)
    cv2.waitKey(0)
    return pillars_mask
