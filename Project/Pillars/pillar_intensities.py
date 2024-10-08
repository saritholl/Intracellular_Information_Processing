from Pillars.pillars_utils import *
from Pillars.pillars_mask import *
import pickle
from scipy import stats
from Pillars.consts import *
from matplotlib.pyplot import cm
from matplotlib import animation
from sklearn.preprocessing import MinMaxScaler
from sklearn.preprocessing import RobustScaler
from sklearn.preprocessing import StandardScaler

def get_pillar_to_intensities(path, use_cache=True):
    """
    Mapping each pillar to its intensity in every frame
    :param path:
    :return:
    """

    pillar_to_intensities_cache_path = Consts.pillar_to_intensities_cache_path
    if use_cache and Consts.USE_CACHE and os.path.isfile(pillar_to_intensities_cache_path):
        with open(pillar_to_intensities_cache_path, 'rb') as handle:
            pillar2frame_intensity = pickle.load(handle)
            return pillar2frame_intensity

    pillar2last_mask = get_last_img_mask_for_each_pillar(get_all_center_generated_ids(), use_cache)
    pillar2frame_intensity = {}

    images = get_images(path)

    frame_to_alive_pillars_real_locations = get_alive_centers_real_location_by_frame_v2()

    # Saves the actual location used for intensities, for debugging purposes, takes the ID or actual loc (if found)
    frame_to_alive_pillar_loc_used_for_intensities = {}

    for pillar_item in pillar2last_mask.items():
        pillar_id = pillar_item[0]
        mask = pillar_item[1]
        curr_pillar_intensity = []
        for frame_index, frame in enumerate(images):
            alive_pillars_real_locations_in_curr_frame = frame_to_alive_pillars_real_locations[frame_index]
            alive_closest_real_location = None
            used_pillar_location = pillar_id
            if len(alive_pillars_real_locations_in_curr_frame) > 0:
                alive_closest_real_location = min(alive_pillars_real_locations_in_curr_frame,
                                                  key=lambda point: math.hypot(pillar_item[0][1] - point[1],
                                                                            pillar_item[0][0] - point[0]))
                if np.linalg.norm(np.array(alive_closest_real_location) - np.array(pillar_item[0])) < Consts.MAX_DISTANCE_TO_CLOSEST:
                    # Use mask on the new, real actual center location
                    mask = get_mask_for_center(alive_closest_real_location)
                    used_pillar_location = alive_closest_real_location

            if frame_index not in frame_to_alive_pillar_loc_used_for_intensities:
                frame_to_alive_pillar_loc_used_for_intensities[frame_index] = []
            frame_to_alive_pillar_loc_used_for_intensities[frame_index].append(used_pillar_location)

            frame_masked = np.where(mask, frame, 0)

            curr_pillar_intensity.append(np.sum(frame_masked))
        pillar2frame_intensity[pillar_id] = curr_pillar_intensity

    if use_cache and Consts.USE_CACHE:
        with open(pillar_to_intensities_cache_path, 'wb') as handle:
            pickle.dump(pillar2frame_intensity, handle, protocol=pickle.HIGHEST_PROTOCOL)

    # with open(Consts.pillars_alive_location_by_frame_to_gif_cache_path, 'wb') as handle:
    #     pickle.dump(frame_to_alive_pillar_loc_used_for_intensities, handle, protocol=pickle.HIGHEST_PROTOCOL)

    return pillar2frame_intensity


def get_overall_alive_pillars_to_intensities(use_cache=True):
    """
    Mapping only alive pillars to theirs intensity in every frame
    :return:
    """

    # return from shuffled results
    if Consts.SHUFFLE_TS_BETWEEN_CELLS:
        try:
            return Consts.shuffled_ts[Consts.config_name]
        except:
            pass

    if Consts.normalized:
        pillar_intensity_dict = normalized_intensities_by_mean_background_intensity(use_cache)
    else:
        pillar_intensity_dict = get_pillar_to_intensities(get_images_path(), use_cache)

    alive_pillar_ids = get_alive_pillar_ids_overall_v3()

    alive_pillars_dict = {pillar: pillar_intensity_dict[pillar] for pillar in alive_pillar_ids}

    return alive_pillars_dict


def get_alive_pillar_to_intensity_not_norm_by_background_noise(use_cache=True):
    p_to_intens = get_overall_alive_pillars_to_intensities(use_cache=use_cache)
    return p_to_intens


def get_inner_pillar_noise_series(inner_mask_radius=(0, 10), use_cache=True):
    inner_pillar_noise_series_cache_path = Consts.inner_pillar_noise_series_cache_path
    if use_cache and Consts.USE_CACHE and os.path.isfile(inner_pillar_noise_series_cache_path):
        with open(inner_pillar_noise_series_cache_path, 'rb') as handle:
            mean_series = pickle.load(handle)
            return mean_series

    origin_small_mask_radius = Consts.SMALL_MASK_RADIUS
    origin_large_mask_radius = Consts.LARGE_MASK_RADIUS

    ratio_radiuses = get_mask_radiuses({'small_radius': inner_mask_radius[0], 'large_radius': inner_mask_radius[1]})
    Consts.SMALL_MASK_RADIUS = ratio_radiuses['small']
    Consts.LARGE_MASK_RADIUS = ratio_radiuses['large']

    alive_pillars_intens = get_overall_alive_pillars_to_intensities(use_cache=False)
    alive_pillars = list(alive_pillars_intens.keys())
    alive_pillars_str = [str(p) for p in alive_pillars]

    inner_pillars_intensity_df = pd.DataFrame.from_dict(alive_pillars_intens, orient='index')
    inner_pillars_intensity_df = inner_pillars_intensity_df.transpose()
    inner_pillars_intensity_df.columns = alive_pillars_str

    # normalized intensity by the avg intensity per frame
    mean_series = inner_pillars_intensity_df.mean(axis=1)

    Consts.SMALL_MASK_RADIUS = origin_small_mask_radius
    Consts.LARGE_MASK_RADIUS = origin_large_mask_radius

    if use_cache and Consts.USE_CACHE:
        with open(inner_pillar_noise_series_cache_path, 'wb') as handle:
            pickle.dump(mean_series, handle, protocol=pickle.HIGHEST_PROTOCOL)

    return mean_series


def get_pillar_to_intensity_norm_by_inner_pillar_noise(inner_mask_radius=(0, 10), use_cache=True):
    if Consts.SHUFFLE_TS_BETWEEN_CELLS:
        use_cache = False

    pillar_to_intensities_norm_by_noise_cache_path = Consts.pillar_to_intensities_norm_by_noise_cache_path
    if use_cache and Consts.USE_CACHE and os.path.isfile(pillar_to_intensities_norm_by_noise_cache_path):
        with open(pillar_to_intensities_norm_by_noise_cache_path, 'rb') as handle:
            ring_pillars_to_norm_by_inner_pillar_intens = pickle.load(handle)
            return ring_pillars_to_norm_by_inner_pillar_intens

    ring_alive_pillars_to_intensity = get_overall_alive_pillars_to_intensities(use_cache=use_cache)

    mean_series = get_inner_pillar_noise_series(inner_mask_radius=inner_mask_radius, use_cache=True)

    mean_series = mean_series.iloc[:len(list(ring_alive_pillars_to_intensity.values())[0])]

    alive_pillars = list(ring_alive_pillars_to_intensity.keys())
    alive_pillars_str = [str(p) for p in alive_pillars]

    ring_pillars_intensity_df = pd.DataFrame.from_dict(ring_alive_pillars_to_intensity, orient='index')
    ring_pillars_intensity_df = ring_pillars_intensity_df.transpose()
    ring_pillars_intensity_df.columns = alive_pillars_str

    ring_df_subtracted = ring_pillars_intensity_df.subtract(mean_series, axis=0)
    ring_pillars_to_norm_by_inner_pillar_intens = {tuple(map(int, col[1:-1].split(', '))): values.tolist() for col, values in
                                    ring_df_subtracted.items()}

    if use_cache and Consts.USE_CACHE:
        with open(pillar_to_intensities_norm_by_noise_cache_path, 'wb') as handle:
            pickle.dump(ring_pillars_to_norm_by_inner_pillar_intens, handle, protocol=pickle.HIGHEST_PROTOCOL)

    return ring_pillars_to_norm_by_inner_pillar_intens


def pillar_to_inner_intensity(inner_mask_radius=(0, 10)):
    origin_small_mask_radius = Consts.SMALL_MASK_RADIUS
    origin_large_mask_radius = Consts.LARGE_MASK_RADIUS

    ratio_radiuses = get_mask_radiuses({'small_radius': inner_mask_radius[0], 'large_radius': inner_mask_radius[1]})
    Consts.SMALL_MASK_RADIUS = ratio_radiuses['small']
    Consts.LARGE_MASK_RADIUS = ratio_radiuses['large']

    alive_pillars_to_inner_intens = get_overall_alive_pillars_to_intensities(use_cache=False)

    Consts.SMALL_MASK_RADIUS = origin_small_mask_radius
    Consts.LARGE_MASK_RADIUS = origin_large_mask_radius

    return alive_pillars_to_inner_intens


def pillar_to_inner_intensity_norm_by_noise(mask_radius=(0, 10), radiuses=(0, 10)):
    origin_small_mask_radius = Consts.SMALL_MASK_RADIUS
    origin_large_mask_radius = Consts.LARGE_MASK_RADIUS

    mean_series = get_inner_pillar_noise_series((0, 10))

    ratio_radiuses = get_mask_radiuses({'small_radius': radiuses[0], 'large_radius': radiuses[1]})
    Consts.SMALL_MASK_RADIUS = ratio_radiuses['small']
    Consts.LARGE_MASK_RADIUS = ratio_radiuses['large']
    alive_pillars_to_intensity = get_overall_alive_pillars_to_intensities(use_cache=False)
    alive_pillars = list(alive_pillars_to_intensity.keys())
    alive_pillars_str = [str(p) for p in alive_pillars]
    pillars_intensity_df = pd.DataFrame.from_dict(alive_pillars_to_intensity, orient='index')
    pillars_intensity_df = pillars_intensity_df.transpose()
    pillars_intensity_df.columns = alive_pillars_str
    df_subtracted = pillars_intensity_df.subtract(mean_series, axis=0)
    pillars_to_norm_intens = {tuple(map(int, col[1:-1].split(', '))): values.tolist() for col, values in
                                       df_subtracted.items()}

    # Return to default values
    Consts.SMALL_MASK_RADIUS = origin_small_mask_radius
    Consts.LARGE_MASK_RADIUS = origin_large_mask_radius

    return pillars_to_norm_intens


def min_max_intensity_normalization(pillar_intensity_dict):
    min_max_scaler = MinMaxScaler()
    normalized_p_to_intens = {key: min_max_scaler.fit_transform(np.array(value).reshape(-1, 1)).flatten() for
                              key, value in pillar_intensity_dict.items()}

    return normalized_p_to_intens


def robust_intensity_normalization(pillar_intensity_dict):
    scaler = RobustScaler()
    normalized_p_to_intens = {key: scaler.fit_transform(np.array(value).reshape(-1, 1)).flatten() for
                              key, value in pillar_intensity_dict.items()}

    return normalized_p_to_intens


def zscore_intensity_normalization(pillar_intensity_dict):
    scaler = StandardScaler()
    normalized_p_to_intens = {key: scaler.fit_transform(np.array(value).reshape(-1, 1)).flatten() for
                              key, value in pillar_intensity_dict.items()}

    return normalized_p_to_intens


def normalized_intensities_by_max_background_intensity():
    """
    Normalization of pillars intensities by the maximum intensity of the background
    :return:
    """
    alive_pillars = get_overall_alive_pillars_to_intensities()
    all_pillars = get_pillar_to_intensities(get_images_path())
    background_pillars_intensities = {pillar: all_pillars[pillar] for pillar in all_pillars.keys() if
                                      pillar not in alive_pillars}
    intensity_values_lst = list(background_pillars_intensities.values())
    max_int = max(max(intensity_values_lst, key=max))
    for pillar_item in all_pillars.items():
        for i, intensity in enumerate(pillar_item[1]):
            sub_int = int(intensity) - int(max_int)
            if sub_int > 0:
                all_pillars[pillar_item[0]][i] = sub_int
            else:
                all_pillars[pillar_item[0]][i] = 0

    return all_pillars


def normalized_intensities_by_mean_background_intensity(use_cache=True):
    """
    Normalization of pillars intensities by the mean intensity of the background
    :return:
    """
    alive_pillars = get_alive_pillar_ids_in_last_frame_v3()
    all_pillars = get_pillar_to_intensities(get_images_path(), use_cache)
    background_pillars_intensities = {pillar: all_pillars[pillar] for pillar in all_pillars.keys() if
                                      pillar not in alive_pillars}

    background_intensity_values_lst = list(background_pillars_intensities.values())
    avg_intensity_in_frame = np.mean(background_intensity_values_lst, axis=0)
    for pillar_item in all_pillars.items():
        for i, intensity in enumerate(pillar_item[1]):
            sub_int = int(intensity) - avg_intensity_in_frame[i]
            all_pillars[pillar_item[0]][i] = sub_int

    return all_pillars


def normalized_intensities_by_zscore():
    """
    Normalization of pillars intensities by z-score
    :return:
    """
    all_pillars = get_pillar_to_intensities(get_images_path())
    all_pillars_int_lst = list(all_pillars.values())
    all_pillars_zscore_int = stats.zscore(all_pillars_int_lst, axis=1)

    for i, pillar_item in enumerate(all_pillars.items()):
        for j, intensity in enumerate(pillar_item[1]):
            all_pillars[pillar_item[0]][j] = all_pillars_zscore_int[i][j]

    return all_pillars


def get_cell_avg_intensity():
    # p_to_intens = get_overall_alive_pillars_to_intensities()
    p_to_intens = get_pillar_to_intensity_norm_by_inner_pillar_noise()
    frame_to_alive_pillars = get_alive_center_ids_by_frame_v3()
    alive_pillars_to_frame = {}
    for frame, alive_pillars_in_frame in frame_to_alive_pillars.items():
        for alive_pillar in alive_pillars_in_frame:
            if alive_pillar not in alive_pillars_to_frame:
                alive_pillars_to_frame[alive_pillar] = frame

    pillars_avg_intens = {}
    for p, intens in p_to_intens.items():
        start_living_frame = alive_pillars_to_frame[p]
        avg_p_intens = np.mean(intens[start_living_frame:])
        pillars_avg_intens[p] = avg_p_intens

    total_avg_intensity = np.mean(list(pillars_avg_intens.values()))
    return total_avg_intensity, pillars_avg_intens


def get_cell_avg_ts(p_to_intens=None):
    # p_to_intens = get_overall_alive_pillars_to_intensities()
    if p_to_intens is None:
        p_to_intens = get_pillar_to_intensity_norm_by_inner_pillar_noise()
    frame_to_alive_pillars = get_alive_center_ids_by_frame_v3()
    alive_pillars_to_frame = {}
    for frame, alive_pillars_in_frame in frame_to_alive_pillars.items():
        for alive_pillar in alive_pillars_in_frame:
            if alive_pillar not in alive_pillars_to_frame:
                alive_pillars_to_frame[alive_pillar] = frame

    avg_ts = []
    total_frames = len(list(p_to_intens.values())[0])
    for frame in range(total_frames):
        intens_in_frame = []
        for p, intens in p_to_intens.items():
            if alive_pillars_to_frame[p] <= frame:
                intens_in_frame.append(intens[frame])
        frame_avg_intens = np.mean(intens_in_frame)
        avg_ts.append(frame_avg_intens)

    return avg_ts


def show_pillars_location_by_frame(frame_to_alive_pillar_loc_used_for_intensities):
    all_images = get_images(get_images_path())
    frame_to_alive_pillars = get_alive_center_ids_by_frame_v3()  # get_frame_to_alive_pillars_by_same_mask(pillar2mask)

    fig = plt.figure()
    ax = fig.add_subplot()

    def animate(i):
        ax.clear()

        curr_frame = i
        pillars_loc = frame_to_alive_pillar_loc_used_for_intensities[curr_frame]

        alive_pillars_loc = [pillar_loc for pillar_loc in pillars_loc if show_pillars_location_by_frame_is_alive(pillar_loc, frame_to_alive_pillars[curr_frame])]

        y = [p[0] for p in alive_pillars_loc]
        x = [p[1] for p in alive_pillars_loc]
        scatter_size = [3 for center in alive_pillars_loc]

        ax.scatter(x, y, s=scatter_size, color='blue')

        ax.imshow(all_images[i % len(all_images)], cmap=plt.cm.gray)

    ani = animation.FuncAnimation(fig, animate, frames=len(all_images), interval=100)

    # Writer = animation.writers['ffmpeg']
    # writer = Writer(fps=20, metadata=dict(artist='Me'), bitrate=1800)
    # writer = animation.FFMpegWriter(fps=10)
    #
    # writer = animation.PillowWriter(fps=10000)
    #
    # if Consts.RESULT_FOLDER_PATH is not None:
    #     ani.save(Consts.RESULT_FOLDER_PATH + "/peripheral_pillars.gif", dpi=300, writer=writer)
    #     plt.close()  # close the figure window

    plt.show()


def show_pillars_location_by_frame_is_alive(pillar_loc, frame_to_alive_pillars):
    alive_closest_real_location = min(frame_to_alive_pillars,
                                      key=lambda point: math.hypot(pillar_loc[1] - point[1],
                                                                   pillar_loc[0] - point[0]))
    if np.linalg.norm(
            np.array(alive_closest_real_location) - np.array(pillar_loc)) < Consts.MAX_DISTANCE_TO_CLOSEST:
       return True
    return False
