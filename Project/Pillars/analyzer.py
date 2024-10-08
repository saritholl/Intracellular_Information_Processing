from scipy.stats import pearsonr, kendalltau
from scipy import stats
from scipy.stats import ttest_ind
from Pillars.pillar_intensities import *
from Pillars.pillars_utils import *
from Pillars.pillar_neighbors import *
from Pillars.consts import *
# from Pillars.visualization import *
# from Pillars.granger_causality_test import *
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import networkx as nx
from networkx.algorithms import core
import community
import statsmodels.api as sm
from sklearn.cluster import DBSCAN
import scipy.fftpack
from skimage.segmentation import slic
from skimage import io, color, filters, segmentation, util, exposure, restoration, feature, morphology, measure
from scipy import ndimage as ndi
from sklearn.preprocessing import MinMaxScaler
import torch
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv
from collections import deque
from math import atan2, degrees
from skimage.util import img_as_float
from skimage.segmentation import mark_boundaries
import matplotlib.colors as mcolors
from fastdtw import fastdtw
# from Pillars.slic import *
from sklearn.metrics import mean_squared_error
from scipy.spatial.distance import euclidean
from scipy.stats import wasserstein_distance
from sklearn.manifold import TSNE
import seaborn as sns


def get_correlations_between_neighboring_pillars(pillar_to_pillars_dict):
    """
    Listing all correlations between pillar and its neighbors
    :param pillar_to_pillars_dict:
    :return:
    """
    all_corr = get_all_pillars_correlations()

    correlations = []
    for pillar, nbrs in pillar_to_pillars_dict.items():
        for n in nbrs:
            correlations.append(all_corr[str(pillar)][str(n)])

    return correlations


def get_alive_pillars_correlation():
    """
    Create dataframe of correlation between alive pillars only
    :return:
    """
    path = get_alive_pillars_corr_path()

    if Consts.USE_CACHE and os.path.isfile(path):
        with open(path, 'rb') as handle:
            correlation = pickle.load(handle)
            return correlation

    relevant_pillars_dict = get_pillar_to_intensity_norm_by_inner_pillar_noise()

    pillar_intensity_df = pd.DataFrame({str(k): v for k, v in relevant_pillars_dict.items()})
    alive_pillars_corr = pillar_intensity_df.corr()
    if Consts.USE_CACHE:
        with open(path, 'wb') as handle:
            pickle.dump(alive_pillars_corr, handle, protocol=pickle.HIGHEST_PROTOCOL)

    return alive_pillars_corr


def get_alive_pillars_correlations_with_running_frame_windows():
    if Consts.USE_CACHE and os.path.isfile(Consts.alive_pillars_correlations_with_running_frame_windows_cache_path):
        with open(Consts.alive_pillars_correlations_with_running_frame_windows_cache_path, 'rb') as handle:
            alive_pillars_correlations_with_running_frame_windows = pickle.load(handle)
            return alive_pillars_correlations_with_running_frame_windows

    pillar_intensity_dict = get_pillar_to_intensity_norm_by_inner_pillar_noise()

    all_pillar_intensity_df = pd.DataFrame({str(k): v for k, v in pillar_intensity_dict.items()})

    all_pillar_intensity_df_array = np.array_split(all_pillar_intensity_df, Consts.FRAME_WINDOWS_AMOUNT)

    alive_pillars_correlations_with_running_frame_windows = [df.corr(method=Consts.CORRELATION) for df in
                                                             all_pillar_intensity_df_array]

    if Consts.USE_CACHE:
        with open(Consts.alive_pillars_correlations_with_running_frame_windows_cache_path, 'wb') as handle:
            pickle.dump(alive_pillars_correlations_with_running_frame_windows, handle, protocol=pickle.HIGHEST_PROTOCOL)

    return alive_pillars_correlations_with_running_frame_windows


def get_alive_pillars_correlations_frame_windows(frame_window=Consts.FRAME_WINDOWS_AMOUNT):
    if Consts.USE_CACHE and os.path.isfile(Consts.alive_pillars_correlations_frame_windows_cache_path):
        with open(Consts.alive_pillars_correlations_frame_windows_cache_path, 'rb') as handle:
            pillars_corrs_frame_window = pickle.load(handle)
            return pillars_corrs_frame_window

    pillar_intensity_dict = get_pillar_to_intensity_norm_by_inner_pillar_noise()

    all_pillar_intensity_df = pd.DataFrame({str(k): v for k, v in pillar_intensity_dict.items()})

    all_pillar_intensity_df_array = np.array_split(all_pillar_intensity_df, frame_window)

    pillars_corrs_frame_window = []
    new_df = None
    for i, df in enumerate(all_pillar_intensity_df_array):
        if i == 0:
            new_df = df
        else:
            new_df = new_df.append(df)

        pillars_corrs_frame_window.append(new_df.corr(method=Consts.CORRELATION))

    if Consts.USE_CACHE:
        with open(Consts.alive_pillars_correlations_frame_windows_cache_path, 'wb') as handle:
            pickle.dump(pillars_corrs_frame_window, handle, protocol=pickle.HIGHEST_PROTOCOL)

    return pillars_corrs_frame_window


# Todo: here we have exception
def get_top_pairs_corr_in_each_frames_window(n=5, neighbor_pairs=True):
    correlations = get_alive_pillars_symmetric_correlation()
    neighbors_dict = get_alive_pillars_to_alive_neighbors()
    sorted_correlations = correlations.where(
        np.triu(np.ones(correlations.shape), k=1).astype(bool)).stack().sort_values(ascending=False)
    corr_frames_wind = get_alive_pillars_correlations_frame_windows()
    i = 0
    top_pairs_corr_in_each_frames_window = {}
    for pillars, value in sorted_correlations.items():
        if i == n:
            break
        if neighbor_pairs:
            if eval(pillars[0]) not in neighbors_dict[eval(pillars[1])]:
                continue
        pair_corr_in_each_frames_window = []
        for df in corr_frames_wind:
            corr = df.loc[pillars[0], pillars[1]]
            pair_corr_in_each_frames_window.append(corr)
        top_pairs_corr_in_each_frames_window[pillars] = pair_corr_in_each_frames_window
        i += 1

    return top_pairs_corr_in_each_frames_window


def get_number_of_neighboring_pillars_in_top_correlations(top=10):
    correlations = get_alive_pillars_symmetric_correlation()
    neighbors_dict = get_alive_pillars_to_alive_neighbors()
    sorted_correlations = correlations.where(
        np.triu(np.ones(correlations.shape), k=1).astype(bool)).stack().sort_values(ascending=False)
    num_of_neighboring_pairs_in_top_corrs = 0
    for i in range(top):
        pillars = sorted_correlations.index[i]
        if eval(pillars[0]) in neighbors_dict[eval(pillars[1])]:
            num_of_neighboring_pairs_in_top_corrs += 1

    print('number of neighboring pillars pairs in the top ' + str(top) + ' correlations: ' + str(
        num_of_neighboring_pairs_in_top_corrs))
    return num_of_neighboring_pairs_in_top_corrs


def get_alive_pillars_corr_path():
    """
    Get the cached correlation of alive pillars
    :return:
    """
    if Consts.normalized:
        path = Consts.correlation_alive_normalized_cache_path
    else:
        path = Consts.correlation_alive_not_normalized_cache_path

    return path


def get_all_pillars_correlations():
    """
    Create dataframe of correlation between all pillars
    :return:
    """
    path = get_all_pillars_corr_path()

    if Consts.USE_CACHE and os.path.isfile(path):
        with open(path, 'rb') as handle:
            correlation = pickle.load(handle)
            return correlation

    if Consts.normalized:
        pillar_intensity_dict = normalized_intensities_by_mean_background_intensity()
    else:
        pillar_intensity_dict = get_pillar_to_intensities(get_images_path())

    all_pillar_intensity_df = pd.DataFrame({str(k): v for k, v in pillar_intensity_dict.items()})
    if Consts.CORRELATION == "pearson":
        all_pillars_corr = all_pillar_intensity_df.corr()
    if Consts.CORRELATION == "kendall":
        all_pillars_corr = all_pillar_intensity_df.corr(method='kendall')

    if Consts.USE_CACHE:
        with open(path, 'wb') as handle:
            pickle.dump(all_pillars_corr, handle, protocol=pickle.HIGHEST_PROTOCOL)

    return all_pillars_corr


def get_all_pillars_correlations_frame_windows():
    # TODO: cache

    if Consts.normalized:
        pillar_intensity_dict = normalized_intensities_by_mean_background_intensity()
    else:
        pillar_intensity_dict = get_pillar_to_intensities(get_images_path())

    all_pillar_intensity_df = pd.DataFrame({str(k): v for k, v in pillar_intensity_dict.items()})

    all_pillar_intensity_df_array = np.array_split(all_pillar_intensity_df, Consts.FRAME_WINDOWS_AMOUNT)

    return [df.corr(method=Consts.CORRELATION) for df in all_pillar_intensity_df_array]


def get_all_pillars_corr_path():
    """
    Get the cached correlation of all pillars
    :return:
    """
    if Consts.normalized:
        path = Consts.all_pillars_correlation_normalized_cache_path
    else:
        path = Consts.all_pillars_correlation_not_normalized_cache_path

    return path


def get_alive_pillars_symmetric_correlation(frame_start=None, frame_end=None, use_cache=True,
                                            pillar_to_intensities_dict=None, norm_by_noise=True):
    """
    Create dataframe of alive pillars correlation as the correlation according to
    maximum_frame(pillar a start to live, pillar b start to live) -> correlation(a, b) == correlation(b, a)
    :return:
    """

    if Consts.SHUFFLE_TS_BETWEEN_CELLS:
        use_cache = False

    origin_frame_start = frame_start
    origin_frame_end = frame_end
    if norm_by_noise and use_cache and origin_frame_start is None and origin_frame_end is None and Consts.USE_CACHE and os.path.isfile(
            Consts.alive_pillars_sym_corr_norm_by_inner_p_noise_cache_path):
        with open(Consts.alive_pillars_sym_corr_norm_by_inner_p_noise_cache_path, 'rb') as handle:
            alive_pillars_symmetric_correlation = pickle.load(handle)
            return alive_pillars_symmetric_correlation
    if not norm_by_noise and use_cache and origin_frame_start is None and origin_frame_end is None and Consts.USE_CACHE and os.path.isfile(
            Consts.alive_pillars_sym_corr_cache_path):
        with open(Consts.alive_pillars_sym_corr_cache_path, 'rb') as handle:
            alive_pillars_symmetric_correlation = pickle.load(handle)
            return alive_pillars_symmetric_correlation

    frame_to_alive_pillars = get_alive_center_ids_by_frame_v3()  # get_frame_to_alive_pillars_by_same_mask(pillar2mask)

    if frame_start is None:
        frame_start = 0
    if frame_end is None:
        frame_end = len(frame_to_alive_pillars)

    alive_pillars_to_start_living_frame = {}
    for curr_frame, alive_pillars_in_frame in frame_to_alive_pillars.items():
        if frame_start <= curr_frame <= frame_end:
            for alive_pillar in alive_pillars_in_frame:
                if alive_pillar not in alive_pillars_to_start_living_frame:
                    alive_pillars_to_start_living_frame[alive_pillar] = curr_frame

    if pillar_to_intensities_dict:
        pillars_intens = pillar_to_intensities_dict
    elif norm_by_noise:
        pillars_intens = get_pillar_to_intensity_norm_by_inner_pillar_noise(inner_mask_radius=(0, 10),
                                                                            use_cache=use_cache)
    else:
        pillars_intens = get_overall_alive_pillars_to_intensities(use_cache=use_cache)

    alive_pillars = list(pillars_intens.keys())
    alive_pillars_str = [str(p) for p in alive_pillars]
    pillars_corr = pd.DataFrame(0.0, index=alive_pillars_str, columns=alive_pillars_str)
    # pillars_intens = zscore_intensity_normalization(pillars_intens)
    # Symmetric correlation - calc correlation of 2 pillars start from the frame they are both alive: maxFrame(A, B)
    for p1 in alive_pillars_to_start_living_frame:
        p1_living_frame = alive_pillars_to_start_living_frame[p1]
        for p2 in alive_pillars_to_start_living_frame:
            p2_living_frame = alive_pillars_to_start_living_frame[p2]
            both_alive_frame = max(p1_living_frame, p2_living_frame)
            p1_relevant_intens = pillars_intens[p1][both_alive_frame:frame_end]
            p2_relevant_intens = pillars_intens[p2][both_alive_frame:frame_end]
            # b/c of this, even if pillar is alive for only 2 frames, we will calculate the correlation,
            # if we will increase 1 to X it means it needs to live for at least X frames to calc correlation for
            if len(p1_relevant_intens) > 1 and len(p2_relevant_intens) > 1:
                if Consts.CORRELATION == "pearson":
                    pillars_corr.loc[str(p2), str(p1)] = pearsonr(p1_relevant_intens, p2_relevant_intens)[0]
                if Consts.CORRELATION == "kendall":
                    pillars_corr.loc[str(p2), str(p1)] = kendalltau(p1_relevant_intens, p2_relevant_intens)[0]

    if norm_by_noise and use_cache and origin_frame_start is None and origin_frame_end is None and Consts.USE_CACHE:
        with open(Consts.alive_pillars_sym_corr_norm_by_inner_p_noise_cache_path, 'wb') as handle:
            pickle.dump(pillars_corr, handle, protocol=pickle.HIGHEST_PROTOCOL)
    if not norm_by_noise and use_cache and origin_frame_start is None and origin_frame_end is None and Consts.USE_CACHE:
        with open(Consts.alive_pillars_sym_corr_cache_path, 'wb') as handle:
            pickle.dump(pillars_corr, handle, protocol=pickle.HIGHEST_PROTOCOL)

    return pillars_corr


def get_all_pillars_symmetric_correlation():
    """
    Create dataframe of alive pillars correlation as the correlation according to
    maximum_frame(pillar a start to live, pillar b start to live) -> correlation(a, b) == correlation(b, a)
    :return:
    """

    centers = get_all_center_generated_ids()

    frame_end = len(get_alive_center_ids_by_frame_v3())

    pillars_intens = get_pillar_to_intensities(get_images_path(), use_cache=False)
    pillars_str = [str(p) for p in list(pillars_intens.keys())]
    pillars_corr = pd.DataFrame(0.0, index=pillars_str, columns=pillars_str)

    # Symmetric correlation - calc correlation of 2 pillars start from the frame they are both alive: maxFrame(A, B)
    for p1 in centers:
        for p2 in centers:
            p1_relevant_intens = pillars_intens[p1]
            p2_relevant_intens = pillars_intens[p2]
            # b/c of this, even if pillar is alive for only 2 frames, we will calculate the correlation,
            # if we will increase 1 to X it means it needs to live for at least X frames to calc correlation for
            if len(p1_relevant_intens) > 1 and len(p2_relevant_intens) > 1:
                if Consts.CORRELATION == "pearson":
                    pillars_corr.loc[str(p2), str(p1)] = pearsonr(p1_relevant_intens, p2_relevant_intens)[0]
                if Consts.CORRELATION == "kendall":
                    pillars_corr.loc[str(p2), str(p1)] = kendalltau(p1_relevant_intens, p2_relevant_intens)[0]

    return pillars_corr


def get_indirect_neighbors_correlation(pillar_location, only_alive=True):
    """
    Create dataframe of correlation between pillar and its indirect neighbors (start from neighbors level 2)
    :param pillar_location:
    :param only_alive:
    :return:
    """
    if only_alive:
        pillars_corr = get_alive_pillars_correlation()
    else:
        pillars_corr = get_all_pillars_correlations()

    pillar_directed_neighbors = get_pillar_directed_neighbors(pillar_location)

    pillar_directed_neighbors_str = []
    for tup in pillar_directed_neighbors:
        if tup != pillar_location:
            pillar_directed_neighbors_str.append(str(tup))
    pillars_corr = pillars_corr.drop(pillar_directed_neighbors_str, axis=0)
    pillars_corr = pillars_corr.drop(pillar_directed_neighbors_str, axis=1)

    return pillars_corr


def get_neighbors_avg_correlation(correlations_df, neighbors_dict):
    sym_corr = set()
    for pillar, nbrs in neighbors_dict.items():
        for nbr in nbrs:
            if str(nbr) in correlations_df and str(pillar) in correlations_df:
                sym_corr.add(correlations_df[str(pillar)][str(nbr)])
    corrs = np.array(list(sym_corr))
    mean_corr = np.mean(corrs)
    mean_corr = format(mean_corr, ".3f")
    return mean_corr, corrs


def get_neighbors_to_correlation(correlations_df, neighbors_dict):
    corrs_dict = {}
    for pillar, nbrs in neighbors_dict.items():
        for nbr in nbrs:
            if str(nbr) in correlations_df and str(pillar) in correlations_df and \
                    (pillar, nbr) not in corrs_dict and (nbr, pillar) not in corrs_dict:
                corrs_dict[(pillar, nbr)] = correlations_df[str(pillar)][str(nbr)]

    return corrs_dict


def get_non_neighbors_mean_correlation(correlations_df, neighbors_dict):
    correlation_list = []
    df = correlations_df.mask(np.tril(np.ones(correlations_df.shape)).astype(np.bool))
    for pillar1 in df.columns:
        for pillar2 in df.columns:
            if pillar1 != pillar2 and eval(pillar2) not in neighbors_dict[eval(pillar1)]:
                if math.isnan(df[str(pillar1)][str(pillar2)]):
                    correlation_list.append(df[str(pillar2)][str(pillar1)])
                else:
                    correlation_list.append(df[str(pillar1)][str(pillar2)])

    mean_corr = np.nanmean(correlation_list)
    mean_corr = format(mean_corr, ".3f")
    return mean_corr, correlation_list


def get_non_neighbors_to_correlation_dict(correlations_df, neighbors_dict):
    correlation_dict = {}
    for pillar1 in correlations_df.columns:
        for pillar2 in correlations_df.columns:
            if pillar1 != pillar2 and eval(pillar2) not in neighbors_dict[eval(pillar1)] and \
                    (pillar1, pillar2) not in correlation_dict and (pillar2, pillar1) not in correlation_dict:
                correlation_dict[(eval(pillar1), eval(pillar2))] = correlations_df[pillar1][pillar2]

    return correlation_dict


def get_number_of_inwards_outwards_gc_edges(gc_df):
    """
    Count the number of inward and outward gc edges
    :param gc_df:
    :return:
    """
    all_alive_centers = get_seen_centers_for_mask()
    cell_center = get_center_of_points(all_alive_centers)
    neighbors = get_alive_pillars_to_alive_neighbors()
    inwards = 0
    outwards = 0
    total_edges = 0
    in_edges = []
    out_edges = []

    for col in gc_df.keys():
        int_col = eval(col)
        for row, _ in gc_df.iterrows():
            int_row = eval(row)
            if gc_df[col][row] < Consts.gc_pvalue_threshold and int_row in neighbors[int_col]:
                total_edges += 1
                # ang = math.degrees(math.atan2(center[1] - int_col[1], center[0] - int_col[0]) - math.atan2(int_row[1] - int_col[1], int_row[0] - int_col[0]))
                # ang = ang + 360 if ang < 0 else ang
                ang = get_angle(int_col, int_row, cell_center)
                if math.dist(int_col, cell_center) < math.dist(int_row, cell_center) and ang >= 135:
                    outwards += 1
                    out_edges.append((col, row))
                elif math.dist(int_col, cell_center) > math.dist(int_row, cell_center) and ang <= 45:
                    inwards += 1
                    in_edges.append((col, row))
    if total_edges == 0:
        in_percentage, out_percentage = 0, 0
    else:
        in_percentage = inwards / total_edges
        out_percentage = outwards / total_edges
    print("Number of total edges: " + str(total_edges))
    print("Number of inwards gc edges: " + str(inwards) + " (" + format(in_percentage * 100, ".2f") + "%)")
    print("Number of outwards gc edges: " + str(outwards) + " (" + format(out_percentage * 100, ".2f") + "%)")
    if in_percentage > 0:
        out_in_factor = format(out_percentage / in_percentage, ".3f")
        print("out/in factor: " + str(out_in_factor))
    else:
        out_in_factor = 'inf'
        print("out/in factor: in edges = 0")
    in_percentage = format(in_percentage, ".3f")
    out_percentage = format(out_percentage, ".3f")
    return total_edges, inwards, outwards, in_edges, out_edges, in_percentage, out_percentage, out_in_factor


def get_angle(col, row, center):
    a = np.array([row[0], row[1]])
    b = np.array([col[0], col[1]])
    c = np.array([center[0], center[1]])

    ba = a - b
    bc = c - b

    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    angle = np.arccos(cosine_angle)
    angle = np.degrees(angle)
    return angle


def probability_for_gc_edge(gc_df, random_neighbors=False):
    """

    :param gc_df:
    :param only_alive:
    :return:
    """
    if random_neighbors:
        neighbors = get_random_neighbors()
    else:
        neighbors = get_alive_pillars_to_alive_neighbors()

    num_of_potential_gc_edges = 0
    num_of_actual_gc_edges = 0

    for col in gc_df.keys():
        for row, _ in gc_df.iterrows():
            if eval(row) in neighbors[eval(col)]:
                num_of_potential_gc_edges += 1
                if gc_df[col][row] < Consts.gc_pvalue_threshold:
                    num_of_actual_gc_edges += 1

    prob_for_gc_edge = num_of_actual_gc_edges / num_of_potential_gc_edges

    print("The probability for a gc edge is " + str(prob_for_gc_edge))

    return prob_for_gc_edge


def avg_gc_edge_probability_original_vs_random(gc_df):
    gc_edge_probs_lst = []
    idx = []
    for i in range(10):
        prob = probability_for_gc_edge(gc_df, random_neighbors=True)
        gc_edge_probs_lst.append(prob)
        idx.append(i)
    avg_random_gc_edge_prob = format(np.mean(gc_edge_probs_lst), ".3f")
    std = format(np.std(gc_edge_probs_lst), ".3f")
    print("avg gc edge probability for random " + str(avg_random_gc_edge_prob))
    print("std: " + str(std))
    return gc_edge_probs_lst, avg_random_gc_edge_prob, std


def get_pillar_in_out_degree(gc_df):
    """
    Get from the granger causality network, the in and out degree edges of each pillar
    :param gc_df: granger causality dataframe
    :return: list of in degree edges of all pillars, out degree of all pillars, list of tuples of (pillar, (in degree, out degree))
    """
    gc_edges_only_df = get_gc_edges_df(gc_df)

    pillars_degree_dict = {}
    in_degree_lst = []
    out_degree_lst = []

    for i, pillar in enumerate(gc_df.columns):
        out_degree = gc_edges_only_df[pillar].count()
        in_degree = gc_edges_only_df.iloc[[i]].count().sum()

        out_degree_lst.append(out_degree)
        in_degree_lst.append(in_degree)
        pillars_degree_dict[pillar] = (in_degree, out_degree)

    return in_degree_lst, out_degree_lst, pillars_degree_dict


def get_gc_edges_df(gc_df):
    neighbors = get_alive_pillars_to_alive_neighbors()

    gc_edges_only_df = gc_df.copy()

    for col in gc_df.keys():
        for row, _ in gc_df.iterrows():
            if not (gc_df[col][row] < Consts.gc_pvalue_threshold and eval(row) in neighbors[eval(col)]):
                gc_edges_only_df[col][row] = None

    return gc_edges_only_df


def get_total_gc_edges(gc_df):
    df = get_gc_edges_df(gc_df)

    return df.count().sum()


def get_network_reciprocity(gc_df):
    neighbors = get_alive_pillars_to_alive_neighbors()
    two_sided_edge = 0

    rows = list(gc_df.keys())
    for i, col in enumerate(gc_df.keys()):
        for j in range(i + 1, len(rows)):
            row = rows[j]
            if eval(row) in neighbors[eval(col)] and gc_df[col][row] < Consts.gc_pvalue_threshold and \
                    gc_df[row][col] < Consts.gc_pvalue_threshold:
                two_sided_edge += 2

    total_edges = get_total_gc_edges(gc_df)
    if total_edges == 0:
        print("There are no edges for reciprocity")
        return
    else:
        reciprocity = format(two_sided_edge / total_edges, ".3f")

    print("Reciprocity: " + str(reciprocity))
    return reciprocity


def get_number_of_pillars_with_edges(gc_df):
    df = get_gc_edges_df(gc_df)

    pillars_without_edges = []
    for col in df.columns:
        if df[col].count() == 0:
            if df.loc[col].count() == 0:
                pillars_without_edges.append(col)

    num_pillars_with_edges = len(df) - len(pillars_without_edges)
    return num_pillars_with_edges


def get_network_heterogeneity(gc_df):
    _, _, pillars_degree_rank = get_pillar_in_out_degree(gc_df)
    df = get_gc_edges_df(gc_df)
    sum_hetero = 0

    for col in df.keys():
        for row, _ in gc_df.iterrows():
            if not math.isnan(df[col][row]):
                d_i_out = pillars_degree_rank[col][1]
                d_j_in = pillars_degree_rank[row][0]
                edge_hetero = (1 / d_i_out) + (1 / d_j_in) - (2 / np.sqrt(d_i_out * d_j_in))
                sum_hetero += edge_hetero

    v = get_number_of_pillars_with_edges(gc_df)
    if v == 0:
        print("There are no edges for heterogeneity")
        return
    else:
        g_heterogeneity = (1 / (v - 2 * np.sqrt(v - 1))) * sum_hetero
        g_heterogeneity = format(g_heterogeneity, ".3f")

    print("Heterogeneity: " + str(g_heterogeneity))
    return g_heterogeneity


def get_output_df(output_path_type):
    output_path = get_output_path(output_path_type)

    output_df = pd.read_csv(output_path, index_col=0)
    output_df.drop('passed_stationary', axis=1, inplace=True)

    return output_df


def get_output_path(output_path_type):
    if Consts.inner_cell:
        output_path = './features output/output_inner_cell_' + output_path_type + '.csv'
    else:
        output_path = './features output/output' + output_path_type + '.csv'

    return output_path


def get_pca(output_path_type, n_components, custom_df=None):
    if custom_df is None:
        output_df = get_output_df(output_path_type)
    else:
        output_df = custom_df
    x = StandardScaler().fit_transform(output_df)
    pca = PCA(n_components=n_components)
    principle_comp = pca.fit_transform(x)
    return pca, principle_comp


def extract_ts_features_dict(time_series):
    # Ensure time_series is a NumPy array
    time_series = np.asarray(time_series)

    # Extract features
    features = {
        'mean': np.mean(time_series),
        'std_dev': np.std(time_series),
        'median': np.median(time_series),
        'skewness': stats.skew(time_series),
        'kurtosis': stats.kurtosis(time_series),
        'max_value': np.max(time_series),
        'min_value': np.min(time_series),
        'dominant_freq': np.argmax(np.abs(scipy.fftpack.fft(time_series)))
    }

    return features


def t_test(samp_lst_1, samp_lst_2):
    stat, pval = ttest_ind(samp_lst_1, samp_lst_2)
    print("p-value: " + str(pval))
    return stat, pval


def get_pillars_movement_correlation_df(pillars_movements_dict):
    frame_to_df_pillars_movement_corr = get_list_of_frame_df_pillars_movement_correlation(pillars_movements_dict)
    frame_to_alive_pillars = get_alive_center_ids_by_frame_v3()
    alive_pillars_to_frame = {}
    for frame, alive_pillars_in_frame in frame_to_alive_pillars.items():
        for alive_pillar in alive_pillars_in_frame:
            if alive_pillar not in alive_pillars_to_frame:
                alive_pillars_to_frame[alive_pillar] = frame

    alive_pillars = list(pillars_movements_dict.keys())
    alive_pillars_str = [str(p) for p in alive_pillars]
    pillars_movements_corr_df = pd.DataFrame(0.0, index=alive_pillars_str, columns=alive_pillars_str)

    for p1 in alive_pillars_to_frame:
        p1_living_frame = alive_pillars_to_frame[p1]
        for p2 in alive_pillars_to_frame:
            p2_living_frame = alive_pillars_to_frame[p2]
            both_alive_frame = max(p1_living_frame, p2_living_frame)
            pillars_corrs_list = []
            for i in range(both_alive_frame, len(frame_to_df_pillars_movement_corr)):
                df = frame_to_df_pillars_movement_corr[i]
                corr = df[str(p1)][str(p2)]
                pillars_corrs_list.append(corr)

            avg_corr = np.nanmean(pillars_corrs_list)
            pillars_movements_corr_df.loc[str(p1), str(p2)] = avg_corr

    return pillars_movements_corr_df


def total_movements_percentage(pillars_movements_dict):
    frame_to_alive_pillars = get_alive_center_ids_by_frame_v3()
    alive_pillars_to_frame = {}
    for frame, alive_pillars_in_frame in frame_to_alive_pillars.items():
        for alive_pillar in alive_pillars_in_frame:
            if alive_pillar not in alive_pillars_to_frame:
                alive_pillars_to_frame[alive_pillar] = frame

    total_frames = len(frame_to_alive_pillars)
    total_chances_to_move = 0
    for frame in alive_pillars_to_frame.values():
        pillar_chances_to_move = total_frames - frame - 1
        total_chances_to_move += pillar_chances_to_move

    actual_movements = 0
    for moves in pillars_movements_dict.values():
        for move in moves:
            if move['distance'] != 0:
                actual_movements += 1

    total_movements_percentage = actual_movements / total_chances_to_move
    with open(Consts.RESULT_FOLDER_PATH + "/total_movements_percentage.txt", 'w') as f:
        f.write("total possible movements percentage: " + str(total_movements_percentage))

    return total_movements_percentage


def get_pillars_intensity_movement_correlations():
    """
    To each pillar - calculating the correlation between its intensities vector to its movements vector
    :return: dictionary of the correlation between those vectors to each pillar
    """
    pillars_movements_dict = get_alive_centers_movements_v2()
    p_to_distances_dict = {}
    for p, v_list in pillars_movements_dict.items():
        distances = []
        for move_dict in v_list:
            distances.append(move_dict['distance'])
        p_to_distances_dict[p] = distances
    pillars_dist_movements_df = pd.DataFrame({str(k): v for k, v in p_to_distances_dict.items()})

    pillar_to_intens_dict = get_pillar_to_intensity_norm_by_inner_pillar_noise()
    pillar_intens_df = pd.DataFrame({str(k): v for k, v in pillar_to_intens_dict.items()})
    pillar_intens_df = pillar_intens_df[:-1]

    frame_to_alive_pillars = get_alive_center_ids_by_frame_v3()  # get_frame_to_alive_pillars_by_same_mask(pillar2mask)
    alive_pillars_to_frame = {}
    for frame, alive_pillars_in_frame in frame_to_alive_pillars.items():
        for alive_pillar in alive_pillars_in_frame:
            if alive_pillar not in alive_pillars_to_frame:
                alive_pillars_to_frame[alive_pillar] = frame

    pillars = pillar_intens_df.columns
    all_pillars_intens_dist_corrs = {}
    for p in pillars:
        p_corr = None
        alive_frame = alive_pillars_to_frame[eval(p)]
        pillar_intens_series = pillar_intens_df[p]
        pillars_dist_series = pillars_dist_movements_df[p]
        p_relevant_intens = pillar_intens_series[alive_frame:]
        p_relevant_dist = pillars_dist_series[alive_frame:]
        if len(p_relevant_intens) > 1 and len(p_relevant_dist) > 1:
            p_corr = pearsonr(p_relevant_intens, p_relevant_dist)[0]
        all_pillars_intens_dist_corrs[p] = p_corr

    return all_pillars_intens_dist_corrs


def get_avg_correlation_pillars_intensity_movement():
    all_pillars_intens_dist_corrs = get_pillars_intensity_movement_correlations()
    avg_corr = np.nanmean(list(all_pillars_intens_dist_corrs.values()))

    with open(Consts.RESULT_FOLDER_PATH + "/intens_movement_sync.txt", 'w') as f:
        f.write("The correlation between the actin signal and the pillar movement is: " + str(avg_corr))

    return avg_corr


def get_average_intensity_by_distance():
    pillars_movements_dict = get_alive_centers_movements_v2()
    p_to_distances_dict = {}
    for p, v_list in pillars_movements_dict.items():
        distances = []
        for move_dict in v_list:
            distances.append(move_dict['distance'])
        p_to_distances_dict[p] = distances
    pillars_dist_movements_df = pd.DataFrame({str(k): v for k, v in p_to_distances_dict.items()})

    pillar_to_intens_dict = get_pillar_to_intensity_norm_by_inner_pillar_noise()
    pillar_intens_df = pd.DataFrame({str(k): v for k, v in pillar_to_intens_dict.items()})
    pillar_intens_df = pillar_intens_df[:-1]

    frame_to_alive_pillars = get_alive_center_ids_by_frame_v3()  # get_frame_to_alive_pillars_by_same_mask(pillar2mask)
    alive_pillars_to_frame = {}
    for frame, alive_pillars_in_frame in frame_to_alive_pillars.items():
        for alive_pillar in alive_pillars_in_frame:
            if alive_pillar not in alive_pillars_to_frame:
                alive_pillars_to_frame[alive_pillar] = frame

    # pillars = pillar_intens_df.columns
    # pillar_to_avg_intens_by_dist = {}
    # for p in pillars:
    #     alive_frame = alive_pillars_to_frame[eval(p)]
    #     pillar_intens_series = pillar_intens_df[p]
    #     pillars_dist_series = pillars_dist_movements_df[p]
    #     p_relevant_intens = pillar_intens_series[alive_frame:]
    #     p_relevant_intens = p_relevant_intens.reset_index().drop('index', axis=1).squeeze()
    #     p_relevant_dist = pillars_dist_series[alive_frame:]
    #     p_relevant_dist = p_relevant_dist.reset_index().drop('index', axis=1).squeeze()
    #     p_unique_distances = p_relevant_dist.unique()
    #     pillar_to_avg_intens_by_dist[p] = {}
    #     for dist in p_unique_distances:
    #         distance_indexes = list(p_relevant_dist[p_relevant_dist == dist].index)
    #         avg_intens_by_distance = np.mean([p_relevant_intens[i] for i in distance_indexes])
    #         pillar_to_avg_intens_by_dist[p][dist] = avg_intens_by_distance

    pillar_to_avg_intens_by_dist = {}
    pillars = pillar_intens_df.columns
    for p in pillars:

        intens_when_dist_zero = []
        intens_when_dist_zero_not_zero = []

        p_relevant_intens = pillar_intens_df[p]
        p_relevant_dist = pillars_dist_movements_df[p]
        for i, intens in enumerate(p_relevant_intens):
            if p_relevant_dist[i] == 0:
                intens_when_dist_zero.append(intens)
            else:
                intens_when_dist_zero_not_zero.append(intens)
        pillar_to_avg_intens_by_dist[p] = {"avg_intens_when_dist_zero": np.mean(intens_when_dist_zero),
                                           "avg_intens_when_dist_non_zero": np.mean(
                                               intens_when_dist_zero_not_zero)}

    return pillar_to_avg_intens_by_dist


def get_avg_movement_correlation(movement_correlations_df, neighbors=False):
    sym_corr = set()
    neighbors_dict = get_alive_pillars_to_alive_neighbors()
    for p1 in movement_correlations_df.columns:
        for p2 in movement_correlations_df.columns:
            if p1 != p2:
                if neighbors:
                    if eval(p2) in neighbors_dict[eval(p1)]:
                        sym_corr.add(movement_correlations_df[str(p1)][str(p2)])
                else:
                    if eval(p2) not in neighbors_dict[eval(p1)]:
                        sym_corr.add(movement_correlations_df[str(p1)][str(p2)])

    corr = np.array(list(sym_corr))
    mean_corr = np.nanmean(corr)
    return mean_corr


def correlation_graph():
    corr_df = get_alive_pillars_symmetric_correlation()
    pillar_to_neighbor_dict = get_alive_pillars_to_alive_neighbors()
    weighted_graph = {}
    for p, nbrs in pillar_to_neighbor_dict.items():
        nbrs_weight = {}
        for nbr in nbrs:
            nbrs_weight[nbr] = corr_df[str(p)][str(nbr)]
        weighted_graph[p] = nbrs_weight

    return weighted_graph


def get_peripheral_and_center_pillars_by_frame_according_to_nbrs():
    nbrs_dict = get_alive_pillars_to_alive_neighbors()
    frame_to_alive_pillars = get_alive_center_ids_by_frame_v3()

    frame_to_peripheral_center_dict = {}
    for frame, curr_frame_alive_pillars in frame_to_alive_pillars.items():
        frame_to_peripheral_center_dict[frame] = {}
        peripherals = []
        centers = []
        for p in curr_frame_alive_pillars:
            alive_nbrs = 0
            for nbr in nbrs_dict[p]:
                if nbr in curr_frame_alive_pillars:
                    alive_nbrs += 1
            if alive_nbrs <= Consts.NUM_NEIGHBORS_TO_CONSIDER_PERIPHERAL:
                peripherals.append(p)
            else:
                centers.append(p)

        frame_to_peripheral_center_dict[frame]["peripherals"] = peripherals
        frame_to_peripheral_center_dict[frame]["centrals"] = centers

    return frame_to_peripheral_center_dict


def get_type_of_pillars_to_frames(frame_to_peripheral_center_dict, pillars_type="peripherals"):
    specific_pillars_to_relevant_frames = {}
    all_pillars = []
    for pillars in frame_to_peripheral_center_dict.values():
        pillars_from_type = pillars[pillars_type]
        all_pillars.extend(pillars_from_type)

    all_pillars = set(all_pillars)
    for p in all_pillars:
        frames = []
        for frame, pillars in frame_to_peripheral_center_dict.items():
            if p in pillars[pillars_type]:
                frames.append(frame)
        specific_pillars_to_relevant_frames[p] = frames

    return specific_pillars_to_relevant_frames


def get_pillars_intensity_movement_sync_by_frames(pillar_to_frames_dict):
    """
    To each pillar - calculating the correlation between its intensities vector to its movements vector
    :return: dictionary of the correlation between those vectors to each pillar
    """
    pillars_movements_dict = get_alive_centers_movements_v2()
    p_to_distances_dict = {}
    for p, v_list in pillars_movements_dict.items():
        distances = []
        for move_dict in v_list:
            distances.append(move_dict['distance'])
        p_to_distances_dict[p] = distances
    pillars_dist_movements_df = pd.DataFrame({str(k): v for k, v in p_to_distances_dict.items()})

    pillar_to_intens_dict = get_pillar_to_intensity_norm_by_inner_pillar_noise()
    pillar_intens_df = pd.DataFrame({str(k): v for k, v in pillar_to_intens_dict.items()})
    pillar_intens_df = pillar_intens_df[:-1]

    last_frame_possible = len(list(pillar_to_intens_dict.values())[0]) - 1
    pillars_intens_dist_corrs = {}
    for p, frames in pillar_to_frames_dict.items():
        intensities = []
        moves = []
        for frame in frames:
            if frame < last_frame_possible:
                intensities.append(pillar_intens_df.loc[frame][str(p)])
                moves.append(pillars_dist_movements_df.loc[frame][str(p)])
        if len(intensities) > 1 and len(moves) > 1:
            p_corr = pearsonr(intensities, moves)[0]

            pillars_intens_dist_corrs[p] = p_corr

    return pillars_intens_dist_corrs


def get_avg_correlation_pillars_intensity_movement_peripheral_vs_central(frame_to_peripheral_center_dict):
    periph_p_to_frames = get_type_of_pillars_to_frames(frame_to_peripheral_center_dict, pillars_type="peripherals")
    central_p_to_frames = get_type_of_pillars_to_frames(frame_to_peripheral_center_dict, pillars_type="centrals")

    # # TODO: test only
    # periph_p_to_frames_min2max = {}
    # for pillar, frames in periph_p_to_frames.items():
    #     min_frame = min(frames)
    #     max_frame = max(frames)
    #
    #     periph_p_to_frames_min2max[pillar] = list(range(min_frame, max_frame + 1))
    # periph_p_to_frames = periph_p_to_frames_min2max

    periph_sync = get_pillars_intensity_movement_sync_by_frames(periph_p_to_frames)
    central_sync = get_pillars_intensity_movement_sync_by_frames(central_p_to_frames)
    avg_periph_sync = np.nanmean(list(periph_sync.values()))
    avg_central_sync = np.nanmean(list(central_sync.values()))

    avg_corr_peripheral_vs_central = {
        "peripherals": avg_periph_sync,
        "centrals": avg_central_sync
    }

    # print("avg_periph_sync: " + str(avg_periph_sync))
    # print("avg_central_sync: " + str(avg_central_sync))

    with open(Consts.RESULT_FOLDER_PATH + "/avg_corr_peripheral_vs_central.json", 'w') as f:
        json.dump(avg_corr_peripheral_vs_central, f)

    return avg_periph_sync, avg_central_sync


def get_peripheral_and_center_pillars_by_frame_according_revealing_pillars_and_nbrs(
        pillars_frame_zero_are_central=True):
    """
    peripheral pillars = reveal by the cell along the movie and keep considered as peripheral as long as
    their number of neighbors < Consts.NUMBER_OF_NBRS_TO_CONSIDER_CENTRAL
    :return:
    """
    nbrs_dict = get_alive_pillars_to_alive_neighbors()
    frame_to_alive_pillars = get_alive_center_ids_by_frame_v3()
    first_frame_pillars = list(frame_to_alive_pillars.values())[0]
    if pillars_frame_zero_are_central:
        central_pillars = list(frame_to_alive_pillars.values())[0]
    else:
        central_pillars = []

    frame_to_peripheral_center_dict = {}
    frame_to_peripheral_center_dict[list(frame_to_alive_pillars.keys())[0]] = {"peripherals": [],
                                                                               "centrals": central_pillars}

    for frame, curr_frame_alive_pillars in dict(list(frame_to_alive_pillars.items())[1:]).items():
        frame_to_peripheral_center_dict[frame] = {}
        frame_peiph = []
        frame_centrals = []
        for p in curr_frame_alive_pillars:
            if p in first_frame_pillars:
                # 1. seen pillar is exist in first frame & pillars_frame_zero_are_central == true
                #  ->  frame_centrals.append(p)
                # 2. seen pillar is exist in first frame & pillars_frame_zero_are_central == false
                #  -> nowhere
                if pillars_frame_zero_are_central:
                    frame_centrals.append(p)
            # 3. not in this list -> continue...
            else:
                alive_nbrs = 0
                for n in nbrs_dict[p]:
                    if n in curr_frame_alive_pillars:
                        alive_nbrs += 1
                if alive_nbrs < Consts.NUMBER_OF_NBRS_TO_CONSIDER_CENTRAL:
                    frame_peiph.append(p)
                else:
                    frame_centrals.append(p)

        # central_pillars.extend(frame_centrals)

        frame_to_peripheral_center_dict[frame]["peripherals"] = frame_peiph
        frame_to_peripheral_center_dict[frame]["centrals"] = frame_centrals

    return frame_to_peripheral_center_dict


def get_correlations_in_first_and_second_half_of_exp():
    frames_length = len(get_images(get_images_path()))

    first_half_corrs = get_alive_pillars_symmetric_correlation(0, frames_length // 2)
    second_half_corrs = get_alive_pillars_symmetric_correlation(frames_length // 2, frames_length)
    overall_corrs = get_alive_pillars_symmetric_correlation(0, frames_length)

    return first_half_corrs, second_half_corrs, overall_corrs


def get_correlation_df_with_only_alive_pillars(corr_df):
    corr_df = corr_df.loc[:, (corr_df != 0).any(axis=0)]
    corr_df = corr_df.loc[:, (corr_df != 0).any(axis=1)]

    return corr_df


def correlation_diff(corr1_df, corr2_df):
    return corr2_df - corr1_df


def get_cc_pp_cp_correlations():
    nbrs_dict = get_alive_pillars_to_alive_neighbors()
    frame_to_alive_pillars = get_alive_center_ids_by_frame_v3()
    frame_to_periph_center_dict = get_peripheral_and_center_pillars_by_frame_according_revealing_pillars_and_nbrs(
        pillars_frame_zero_are_central=True)

    results = {}

    for p1, nbrs in nbrs_dict.items():
        for p2 in nbrs:
            if (p1, p2) in results or (p2, p1) in results:
                break
            cc_list = []
            cp_list = []
            prev_sequence = None
            for frame, alive_pillars in frame_to_alive_pillars.items():
                if p1 not in alive_pillars or p2 not in alive_pillars:
                    prev_sequence = None
                else:
                    curr_sequence = find_vert_type(p1, p2, frame, frame_to_periph_center_dict)
                    if curr_sequence == prev_sequence:
                        if curr_sequence == 'cc':
                            cc_list[-1].append(frame)
                        elif curr_sequence == 'cp':
                            cp_list[-1].append(frame)
                    else:
                        prev_sequence = curr_sequence
                        if prev_sequence == 'cc':
                            cc_list.append([frame])
                        elif prev_sequence == 'cp':
                            cp_list.append([frame])

        results[(p1, p2)] = {'cc': cc_list, 'cp': cp_list}

    alive_pillars_to_intensities = get_pillar_to_intensity_norm_by_inner_pillar_noise()

    cc_corr_list = []
    cp_corr_list = []

    for pair, series in results.items():
        p1 = pair[0]
        p2 = pair[1]
        cc_corr = get_correlation_of_lists(alive_pillars_to_intensities, p1, p2, series['cc'])
        if cc_corr is not None:
            cc_corr_list.append(cc_corr)

        cp_corr = get_correlation_of_lists(alive_pillars_to_intensities, p1, p2, series['cp'])
        if cp_corr is not None:
            cp_corr_list.append(cp_corr)

    return {'cc_corr': np.mean(cc_corr_list), 'cp_corr': np.mean(cp_corr_list)}


def get_correlation_of_lists(alive_pillars_to_intensities, p1, p2, series):
    SERIES_MIN_LENGTH = 3

    pair_corrs = []
    for ser in series:
        if len(ser) >= SERIES_MIN_LENGTH:
            p1_intens = alive_pillars_to_intensities[p1][ser[0]:ser[-1] + 1]
            p2_intens = alive_pillars_to_intensities[p2][ser[0]:ser[-1] + 1]

            ser_corr = pearsonr(p1_intens, p2_intens)[0]
            pair_corrs.append(ser_corr)
    if len(pair_corrs) == 0:
        return None
    pair_correlation = np.mean(pair_corrs)
    return pair_correlation


def find_vert_type(pillar_1, pillar_2, frame, frame_to_periph_center_dict):
    peripheral = frame_to_periph_center_dict[frame]['peripherals']
    central = frame_to_periph_center_dict[frame]['centrals']

    if pillar_1 in central and pillar_2 in central:
        return 'cc'

    if pillar_1 in peripheral and pillar_2 in peripheral:
        return 'cp'

    if (pillar_1 in central and pillar_2 in peripheral) or (pillar_1 in peripheral and pillar_2 in central):
        return 'cp'

    print("one of the pillars doens't exist", frame, pillar_1, pillar_2)


def get_neighbours_correlations_by_distance_from_cell_center():
    nbrs_dict = get_alive_pillars_to_alive_neighbors()
    all_corr = get_alive_pillars_symmetric_correlation()
    pillar2middle_img_steps = get_pillar2_middle_img_steps(nbrs_dict)

    distance2corrs = {dis: [] for dis in set(pillar2middle_img_steps.values())}

    seen_pairs = set()

    for p1, nbrs in nbrs_dict.items():
        for p2 in nbrs:
            if (p1, p2) not in seen_pairs and (p2, p1) not in seen_pairs:
                distance = find_vertex_distance_from_center(p1, p2, pillar2middle_img_steps)
                distance2corrs[distance].append(all_corr.loc[str(p1)][str(p2)])
                seen_pairs.add((p1, p2))

    result = {dis: np.mean(corrs) for dis, corrs in distance2corrs.items() if dis != 0}

    return result


def get_pillar2_middle_img_steps(nbrs_dict):
    alive_pillars = list(get_alive_pillars_to_alive_neighbors())
    middle_img = (np.mean([p[0] for p in alive_pillars]), np.mean([p[1] for p in alive_pillars]))
    # this returns only 1 center, change to get more
    closest_pillars_to_middle = min(alive_pillars,
                                    key=lambda alive_pillars:
                                    math.hypot(alive_pillars[1] - middle_img[1],
                                               alive_pillars[0] - middle_img[0]))

    pillar2_middle_img_steps = {}
    for p in alive_pillars:
        distance_from_middle_center = get_path_distance(nbrs_dict, p, closest_pillars_to_middle, alive_pillars)
        pillar2_middle_img_steps[p] = distance_from_middle_center

    pillar2_middle_img_steps[closest_pillars_to_middle] = 0

    return pillar2_middle_img_steps


def get_path_distance(nbrs_dict, source_pillar, dest_pillar, alive_pillars):
    pred = dict([(p, None) for p in alive_pillars])
    dist = dict([(p, None) for p in alive_pillars])

    if not BFS_for_distance_from_middle(nbrs_dict, source_pillar, dest_pillar, alive_pillars, pred, dist):
        print("Given source and destination are not connected")
        return 0

    path = []
    crawl = dest_pillar
    path.append(crawl)

    while pred[crawl] != -1:
        path.append(pred[crawl])
        crawl = pred[crawl]

    return len(path) - 1


def BFS_for_distance_from_middle(nbrs_dict, source_pillar, dest_pillar, alive_pillars, pred, dist):
    queue = []

    visited = dict([(p, False) for p in alive_pillars])

    for p in alive_pillars:
        dist[p] = 1000000
        pred[p] = -1

    visited[source_pillar] = True
    dist[source_pillar] = 0
    queue.append(source_pillar)

    while len(queue) != 0:
        u = queue[0]
        queue.pop(0)
        for nbr_p in nbrs_dict[u]:

            if not visited[nbr_p]:
                visited[nbr_p] = True
                dist[nbr_p] = dist[u] + 1
                pred[nbr_p] = u
                queue.append(nbr_p)

                # We stop BFS when we find
                # destination.
                if nbr_p == dest_pillar:
                    return True

    return False


# def get_correlations_norm_by_noise(mask_radius, radius_tuples):
#     origin_small_mask_radius = Consts.SMALL_MASK_RADIUS
#     origin_large_mask_radius = Consts.LARGE_MASK_RADIUS
#
#     ratio_radiuses = get_mask_radiuses({'small_radius': mask_radius[0], 'large_radius': mask_radius[1]})
#     Consts.SMALL_MASK_RADIUS = ratio_radiuses['small']
#     Consts.LARGE_MASK_RADIUS = ratio_radiuses['large']
#
#     alive_pillars_intens = get_overall_alive_pillars_to_intensities(use_cache=False)
#     alive_pillars = list(alive_pillars_intens.keys())
#     alive_pillars_str = [str(p) for p in alive_pillars]
#
#     inner_pillars_intensity_df = pd.DataFrame.from_dict(alive_pillars_intens, orient='index')
#     inner_pillars_intensity_df = inner_pillars_intensity_df.transpose()
#     inner_pillars_intensity_df.columns = alive_pillars_str
#
#     mean_series = inner_pillars_intensity_df.mean(axis=1)
#
#     map_radius_to_norm_corr = {}
#     for radiuses in radius_tuples:
#         ratio_radiuses = get_mask_radiuses({'small_radius': radiuses[0], 'large_radius': radiuses[1]})
#         Consts.SMALL_MASK_RADIUS = ratio_radiuses['small']
#         Consts.LARGE_MASK_RADIUS = ratio_radiuses['large']
#
#         ring_alive_pillars_to_intensity = get_overall_alive_pillars_to_intensities(use_cache=False)
#         alive_pillars = list(ring_alive_pillars_to_intensity.keys())
#         alive_pillars_str = [str(p) for p in alive_pillars]
#
#         ring_pillars_intensity_df = pd.DataFrame.from_dict(ring_alive_pillars_to_intensity, orient='index')
#         ring_pillars_intensity_df = ring_pillars_intensity_df.transpose()
#         ring_pillars_intensity_df.columns = alive_pillars_str
#
#         ring_corrs_before_norm, _ = get_neighbors_avg_correlation(
#             get_alive_pillars_symmetric_correlation(use_cache=False),
#             get_alive_pillars_to_alive_neighbors())
#
#         ring_df_subtracted = ring_pillars_intensity_df.subtract(mean_series, axis=0)
#         ring_pillars_to_norm_intens = {tuple(map(int, col[1:-1].split(', '))): values.tolist() for col, values in
#                                        ring_df_subtracted.items()}
#
#         # corrs after normalization
#         ring_nbrs_corrs_after_norm, _ = get_neighbors_avg_correlation(
#             get_alive_pillars_symmetric_correlation(use_cache=False,
#                                                     pillar_to_intensities_dict=ring_pillars_to_norm_intens),
#             get_alive_pillars_to_alive_neighbors())
#
#         ring_non_nbrs_corrs_after_norm, _ = get_non_neighbors_mean_correlation(
#             get_alive_pillars_symmetric_correlation(use_cache=False,
#                                                     pillar_to_intensities_dict=ring_pillars_to_norm_intens),
#             get_alive_pillars_to_alive_neighbors())
#
#         map_radius_to_norm_corr[radiuses] = {}
#         map_radius_to_norm_corr[radiuses]['nbrs_corrs'] = ring_nbrs_corrs_after_norm
#         map_radius_to_norm_corr[radiuses]['non_nbrs_corrs'] = ring_non_nbrs_corrs_after_norm
#
#         print("norm by radius:", mask_radius, "curr radius:", radiuses, "before norm:", ring_corrs_before_norm,
#               "after norm:", ring_nbrs_corrs_after_norm)
#
#     # Return to default values
#     Consts.SMALL_MASK_RADIUS = origin_small_mask_radius
#     Consts.LARGE_MASK_RADIUS = origin_large_mask_radius
#
#     return map_radius_to_norm_corr


def find_vertex_distance_from_center(p1, p2, pillar2middle_img_steps):
    return max([pillar2middle_img_steps[p1], pillar2middle_img_steps[p2]])


# simple_swap = replace only intensisies, keep times of living
# Not simple_swap = replace intensisies + live of living
def get_correlations_df_for_mixed_ts(simple_swap=True):
    # Get intensities (in timeseries)
    pillar_intens = get_pillar_to_intensity_norm_by_inner_pillar_noise()
    # Shuffle timeseries (between pillars)
    # if simple_swap:
    # Get a list of the dictionary values
    values = list(pillar_intens.values())
    # Shuffle the list of values in place
    random.shuffle(values)
    # Create a new dictionary with the shuffled values
    shuffled_pillar_intens = {key: value for key, value in zip(pillar_intens.keys(), values)}
    # Calculate neighours-correlation
    corrs_df = get_alive_pillars_symmetric_correlation(use_cache=False,
                                                       pillar_to_intensities_dict=shuffled_pillar_intens)

    return corrs_df


def get_correlations_df_for_mixed_ts_permutations(simple_swap=True):
    np.random.seed(42)
    num_shuffles = 10
    # Get intensities (in timeseries)
    pillar_intens = get_pillar_to_intensity_norm_by_inner_pillar_noise()
    num_pillars = len(pillar_intens)  # Number of pillars
    accumulated_corrs = np.zeros((num_pillars, num_pillars))
    for _ in range(num_shuffles):
        # Shuffle timeseries (between pillars)
        # Get a list of the dictionary values
        values = list(pillar_intens.values())
        # Shuffle the list of values in place
        random.shuffle(values)
        # Create a new dictionary with the shuffled values
        shuffled_pillar_intens = {key: value for key, value in zip(pillar_intens.keys(), values)}
        # Calculate neighours-correlation
        corrs_df = get_alive_pillars_symmetric_correlation(use_cache=False,
                                                           pillar_to_intensities_dict=shuffled_pillar_intens)
        accumulated_corrs += corrs_df.values
    mean_corrs_matrix = accumulated_corrs / num_shuffles

    # Convert the matrix back to a DataFrame with the same row/column labels as the original pillars
    mean_corrs_df = pd.DataFrame(mean_corrs_matrix, index=corrs_df.index, columns=corrs_df.columns)

    return mean_corrs_df


def build_pillars_graph(random_neighbors=False, shuffle_ts=False, draw=False):
    my_G = nx.Graph()
    # nodes_loc_old = get_all_center_generated_ids()
    nodes_loc = get_alive_pillar_ids_overall_v3()
    nodes_loc = list(nodes_loc)
    nodes_loc_y_inverse = [(loc[1], loc[0]) for loc in nodes_loc]
    node_loc2index = {}
    for i in range(len(nodes_loc)):
        node_loc2index[str(nodes_loc[i])] = i
        my_G.add_node(i, pos=nodes_loc[i])

    if random_neighbors:
        neighbors = get_random_neighbors()
    else:
        neighbors = get_alive_pillars_to_alive_neighbors()

    if Consts.only_alive:
        correlation = get_alive_pillars_symmetric_correlation()
    else:
        correlation = get_all_pillars_correlations()

    if shuffle_ts:
        correlation = get_correlations_df_for_mixed_ts()

    # removed_nodes = []
    pillars_pair_to_corr = {}
    for pillar, nbrs in neighbors.items():
        # if len(nbrs) == 0:
        #     node = node_loc2index[str(pillar)]
        #     removed_nodes.append((node, my_G.nodes[node]))
        #     my_G.remove_node(node)
        #     continue
        for nbr in nbrs:
            if (pillar, nbr) not in pillars_pair_to_corr and (nbr, pillar) not in pillars_pair_to_corr:
                if str(nbr) in correlation and str(pillar) in correlation and not np.isnan(
                        correlation[str(pillar)][str(nbr)]):
                    pillars_pair_to_corr[(pillar, nbr)] = (correlation[str(pillar)][str(nbr)])

    def normalize_values(values_dict):
        min_value = min(values_dict.values())
        max_value = max(values_dict.values())
        for k, v in values_dict.items():
            norm_value = (v - min_value) / (max_value - min_value)
            values_dict[k] = norm_value

        return values_dict

    pillars_pair_to_corr = normalize_values(pillars_pair_to_corr)

    for pair, corr in pillars_pair_to_corr.items():
        my_G.add_edge(node_loc2index[str(pair[0])], node_loc2index[str(pair[1])])
        my_G[node_loc2index[str(pair[0])]][node_loc2index[str(pair[1])]]['weight'] = corr

    if draw:
        if nx.get_edge_attributes(my_G, 'weight') == {}:
            return

        edges, weights = zip(*nx.get_edge_attributes(my_G, 'weight').items())

        img = get_last_image_whiten(build_image=Consts.build_image)
        fig, ax = plt.subplots()
        ax.imshow(img, cmap='gray')

        node_idx2loc = {v: k for k, v in node_loc2index.items()}

        # center = nx.center(my_G)
        # node_colors = ['red' if node in center else 'blue' for node in my_G.nodes()]

        nx.draw(my_G, nodes_loc_y_inverse, edgelist=edges, edge_color=weights,
                width=3.0, node_size=50)

        # nx.draw_networkx_labels(my_G, nodes_loc_y_inverse, font_color="whitesmoke", font_size=8)
        # plt.scatter([163.68], [113.55], c='black', s=100, marker='o')
        # plt.scatter([156], [107], c='black', s=100, marker='o')

        sm = plt.cm.ScalarMappable()
        sm.set_array(weights)
        plt.colorbar(sm)

        # plt.scatter(get_image_size()[0]/2, get_image_size()[1]/2, s=250, c="red")

        if Consts.SHOW_GRAPH:
            plt.show()

    return my_G


def nodes_strengths(G, draw=False, color_map_nodes=False, group_nodes_colored=None):
    # Calculate node strengths
    node_strengths = {}
    for node in G.nodes:
        incident_edges = G.edges(node, data='weight')
        strength = sum(weight for _, _, weight in incident_edges) / len(incident_edges) if incident_edges else 0
        node_strengths[node] = round(strength, 2)

    # # Find the median strength
    # median_strength = sorted(node_strengths.values())[len(node_strengths) // 2]

    # Find the strong threshold based on a higher percentile
    # strong_threshold = np.percentile(list(node_strengths.values()), 80)
    strong_threshold = np.sum(list(node_strengths.values())) / len(node_strengths.values())

    # Separate nodes based on their strength compared to the median
    strong_nodes = [node for node, strength in node_strengths.items() if strength > strong_threshold]
    weak_nodes = [node for node, strength in node_strengths.items() if strength <= strong_threshold]

    if draw:
        img = get_last_image_whiten(build_image=Consts.build_image)
        fig, ax = plt.subplots()
        ax.imshow(img, cmap='gray')

        pos = nx.get_node_attributes(G, 'pos')
        nodes_loc_y_inverse = {k: (v[1], v[0]) for k, v in pos.items()}

        if color_map_nodes:
            cmap = cm.get_cmap('coolwarm')
            # norm = plt.Normalize(min(node_strengths.values()), max(node_strengths.values()))
            norm = plt.Normalize(0, 1)
            node_colors = [cmap(norm(node_strengths[node])) for node in G.nodes]
            nx.draw(G, nodes_loc_y_inverse, node_color=node_colors, cmap=cmap)
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            plt.colorbar(sm, label='Strength')
        elif group_nodes_colored is not None:
            node_colors = ['green' if pos[node] in group_nodes_colored else 'grey' for node in G.nodes]
            nx.draw(G, nodes_loc_y_inverse, node_color=node_colors)
            # sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
            # sm.set_array([])
            # plt.colorbar(sm, label='Strength')
        else:
            # Draw strong nodes in one color and weak nodes in another color
            nx.draw_networkx_nodes(G, nodes_loc_y_inverse, nodelist=strong_nodes, node_color='r')
            nx.draw_networkx_nodes(G, nodes_loc_y_inverse, nodelist=weak_nodes, node_color='b')

        # Draw the edges
        nx.draw_networkx_edges(G, nodes_loc_y_inverse)

        # Display the node strengths as labels
        nx.draw_networkx_labels(G, nodes_loc_y_inverse, labels=node_strengths, font_size=8)

        # Show the graph
        plt.axis('off')
        plt.show()

    return node_strengths, strong_nodes, weak_nodes


def nbrs_nodes_similarity_by_strength(G, nodes_strength):
    """
    The similarity here is measured by the subtraction of the two (neighbors or not) pillars strength,
    which their strength is the avg correlation with its neighbors except the correlations between the 2 pillars
    """
    neighbors = get_alive_pillars_to_alive_neighbors()

    pillar_strength_dict = {}
    node_pos_to_idx = {}
    for node_idx in nodes_strength:
        coor = G.nodes[node_idx]['pos']
        node_pos_to_idx[coor] = node_idx
        pillar_strength_dict[coor] = nodes_strength[node_idx]

    similarity_dict = {}
    for pillar, nbrs in neighbors.items():
        for nbr in nbrs:
            if (pillar, nbr) not in similarity_dict and (nbr, pillar) not in similarity_dict:
                pillar_idx = node_pos_to_idx[pillar]
                nbr_idx = node_pos_to_idx[nbr]
                pillar_incident_edges = G.edges(pillar_idx, data='weight')
                nbr_incident_edges = G.edges(nbr_idx, data='weight')
                if len(pillar_incident_edges) <= 1:
                    pillar_strength = 0
                else:
                    pillar_strength = sum(weight for _, n, weight in pillar_incident_edges if n is not nbr_idx) / (
                            len(pillar_incident_edges) - 1) if pillar_incident_edges else 0
                if len(nbr_incident_edges) <= 1:
                    nbr_strength = 0
                else:
                    nbr_strength = sum(weight for _, n, weight in nbr_incident_edges if n is not pillar_idx) / (
                            len(nbr_incident_edges) - 1) if nbr_incident_edges else 0

                diff = abs(pillar_strength - nbr_strength)
                sim = 1 - diff
                similarity_dict[(pillar, nbr)] = (round(diff, 3), round(sim, 3))

    return similarity_dict


def non_nbrs_similarity_by_strength(G, nodes_strength):
    neighbors = get_alive_pillars_to_alive_neighbors()
    pillars = list(neighbors.keys())
    pillar_strength = {}
    for node_idx in nodes_strength:
        coor = G.nodes[node_idx]['pos']
        pillar_strength[coor] = nodes_strength[node_idx]

    similarity_dict = {}
    for pillar1 in pillars:
        for pillar2 in pillars:
            if pillar1 is not pillar2 and (pillar1, pillar2) not in similarity_dict and \
                    (pillar2, pillar1) not in similarity_dict and pillar2 not in neighbors[pillar1]:
                diff = abs(pillar_strength[pillar1] - pillar_strength[pillar2])
                sim = 1 - diff
                similarity_dict[(pillar1, pillar2)] = (round(diff, 3), round(sim, 3))

    return similarity_dict


def get_pillar_to_avg_similarity_dict(nbrs_similarity_dict, non_nbrs_similarity_dict):
    pillars = set([element for tup in list(nbrs_similarity_dict.keys()) for element in tup])

    pillar_to_nbrs_and_non_nbrs_avg_sim = {}
    for p in pillars:
        nbrs_sim = []
        for k, v in nbrs_similarity_dict.items():
            if p in k:
                nbrs_sim.append(v[1])
        avg_nbrs_sim = np.mean(nbrs_sim)
        non_nbrs_sim = []
        for k, v in non_nbrs_similarity_dict.items():
            if p in k:
                non_nbrs_sim.append(v[1])
        avg_non_nbrs_sim = np.mean(non_nbrs_sim)
        pillar_to_nbrs_and_non_nbrs_avg_sim[p] = (avg_nbrs_sim, avg_non_nbrs_sim)

    return pillar_to_nbrs_and_non_nbrs_avg_sim


def topological_distance_to_pair(G, nbrs_corrs_dict, non_nbrs_corrs_dict):
    distance_to_pair = {}

    distance_1 = list(nbrs_corrs_dict.keys())
    distance_to_pair[1] = distance_1

    for k, v in non_nbrs_corrs_dict.items():
        node1_idx = next((i for i, p in G.nodes(data=True) if p.get('pos') == k[0]), None)
        node2_idx = next((i for i, p in G.nodes(data=True) if p.get('pos') == k[1]), None)
        try:
            distance = nx.shortest_path_length(G, source=node1_idx, target=node2_idx)
            if distance not in distance_to_pair:
                distance_to_pair[distance] = []
            distance_to_pair[distance].append(k)
        except:
            continue

    def extract_neighbors(pair_list, node):
        neighbors = set()
        for pair in pair_list:
            if node in pair:
                other_node = pair[0] if pair[1] == node else pair[1]
                neighbors.add(other_node)
        return neighbors

    # p1 = (125, 95)
    # pair_list = list(distance_to_pair[3])
    # pillars_in_dist = list(extract_neighbors(pair_list, p1))
    # img = get_last_image_whiten(build_image=Consts.build_image)
    # fig, ax = plt.subplots()
    # ax.imshow(img, cmap='gray')
    # pos = nx.get_node_attributes(G, 'pos')
    # nodes_loc_y_inverse = {k: (v[1], v[0]) for k, v in pos.items()}
    # pillars_in_dist_inverse = [(p[1], p[0]) for p in pillars_in_dist]
    # node_colors = []
    # for node in list(nodes_loc_y_inverse.values()):
    #     if node in pillars_in_dist_inverse:
    #         node_colors.append('red')
    #     elif (node[1], node[0]) == p1:
    #         node_colors.append('white')
    #     else:
    #         node_colors.append('black')
    # nx.draw(G, nodes_loc_y_inverse, node_color=node_colors)
    # plt.show()

    return distance_to_pair


def nbrs_level_to_correlation(G, nbrs_corrs_dict, non_nbrs_corrs_dict):
    level_to_corrs = {}

    level_1_sims = list(nbrs_corrs_dict.values())
    level_to_corrs[1] = level_1_sims

    for k, v in non_nbrs_corrs_dict.items():
        node1_idx = next((i for i, p in G.nodes(data=True) if p.get('pos') == k[0]), None)
        node2_idx = next((i for i, p in G.nodes(data=True) if p.get('pos') == k[1]), None)
        try:
            level = nx.shortest_path_length(G, source=node1_idx, target=node2_idx)
            if level not in level_to_corrs:
                level_to_corrs[level] = []
            level_to_corrs[level].append(v)
        except:
            continue

    sorted_level_to_similarities = {k: level_to_corrs[k] for k in sorted(level_to_corrs)}

    # keep only the degree in which the number of similarity values is higher than 50% of the largest similarity degree list
    max_list_values = max([len(v) for v in sorted_level_to_similarities.values()])

    cut_dict = {key: value for key, value in sorted_level_to_similarities.items() if
                len(value) >= max_list_values * 0.5 or key == 1}

    return cut_dict


def nbrs_level_to_similarities(G, nbrs_similarity_dict, non_nbrs_similarity_dict):
    level_to_similarities = {}

    level_1_sims = [v[1] for v in nbrs_similarity_dict.values()]
    level_to_similarities[1] = level_1_sims

    for k, v in non_nbrs_similarity_dict.items():
        node1_idx = next((i for i, p in G.nodes(data=True) if p.get('pos') == k[0]), None)
        node2_idx = next((i for i, p in G.nodes(data=True) if p.get('pos') == k[1]), None)
        try:
            level = nx.shortest_path_length(G, source=node1_idx, target=node2_idx)
            if level not in level_to_similarities:
                level_to_similarities[level] = []
            level_to_similarities[level].append(v[1])
        except:
            continue

    sorted_level_to_similarities = {k: level_to_similarities[k] for k in sorted(level_to_similarities)}

    # keep only the degree in which the number of similarity values is higher than 50% of the largest similarity degree list
    max_list_values = max([len(v) for v in sorted_level_to_similarities.values()])

    cut_dict = {key: value for key, value in sorted_level_to_similarities.items() if
                len(value) >= max_list_values * 0.5 or key == 1}

    return cut_dict


def similarity_to_nbrhood_level_correlation(level_to_similarities_dict):
    nbrhood_level_list = list(level_to_similarities_dict.keys())
    simis = list(level_to_similarities_dict.values())
    avgs = [np.mean(sublist) for sublist in simis]
    corr = np.corrcoef(np.array(nbrhood_level_list), avgs)[0][1]

    return corr


def correlation_between_nbrhood_level_to_avg_correlation(level_to_corrs_dict):
    nbrhood_level_list = list(level_to_corrs_dict.keys())
    simis = list(level_to_corrs_dict.values())
    avgs = [np.mean(sublist) for sublist in simis]
    corr = np.corrcoef(np.array(nbrhood_level_list), avgs)[0][1]
    corr, p_value = pearsonr(np.array(nbrhood_level_list), avgs)
    print('correlation:', corr)
    print('p-value:', p_value)

    # topological_distances = []
    # correlations = []
    # for distance, correlation_list in level_to_corrs_dict.items():
    #     for correlation in correlation_list:
    #         topological_distances.append(distance)
    #         correlations.append(correlation)
    # corr, p_value = pearsonr(topological_distances, correlations)

    return corr


def get_core_periphery_pillars():
    neighbors = get_alive_pillars_to_alive_neighbors()
    core = [k for k, v in neighbors.items() if len(v) == 8]
    periphery = [k for k, v in neighbors.items() if len(v) < 8]

    return core, periphery


def get_core_periphery_values_by_strength(core_pillars, periphery_pillars, G, pillars_strength):
    pillar_strength_dict = {}
    for node_idx in pillars_strength:
        coor = G.nodes[node_idx]['pos']
        pillar_strength_dict[coor] = pillars_strength[node_idx]

    core_strength = [v for k, v in pillar_strength_dict.items() if k in core_pillars]
    periphery_strength = [v for k, v in pillar_strength_dict.items() if k in periphery_pillars]

    return core_strength, periphery_strength


def get_core_periphery_values_by_correlation(core_pillars, periphery_pillars):
    corrs = get_alive_pillars_symmetric_correlation()
    nbrs = get_alive_pillars_to_alive_neighbors()

    border_corrs = []
    core_corrs = []
    periphery_corrs = []
    pillars = corrs.columns
    for i in range(len(pillars)):
        for j in range(i + 1, len(pillars)):
            p1 = pillars[i]
            p2 = pillars[j]
            if eval(p1) in nbrs[eval(p2)]:
                corr = corrs[p1][p2]
                if eval(p1) in core_pillars and eval(p2) in core_pillars:
                    core_corrs.append(corr)
                elif eval(p1) in periphery_pillars and eval(p2) in periphery_pillars:
                    periphery_corrs.append(corr)
                else:
                    border_corrs.append(corr)

    return core_corrs, periphery_corrs, border_corrs


def get_core_periphery_values_by_similarity(core_pillars, periphery_pillars, nbrs_similarity_dict):
    border_corrs = []
    core_corrs = []
    periphery_corrs = []
    for pair, sim in nbrs_similarity_dict.items():
        similarity = sim[1]
        p1 = pair[0]
        p2 = pair[1]
        if p1 in core_pillars and p2 in core_pillars:
            core_corrs.append(similarity)
        elif p1 in periphery_pillars and p2 in periphery_pillars:
            periphery_corrs.append(similarity)
        else:
            border_corrs.append(similarity)

    return core_corrs, periphery_corrs, border_corrs


def test_avg_core_periphery_similarity_significance(num_permutations=1000, alpha=0.05):
    G = build_pillars_graph(shuffle_ts=False, draw=False)
    ns, strong_nodes, _ = nodes_strengths(G, draw=False)
    nbrs_sim_dict = nbrs_nodes_similarity_by_strength(G, ns)
    core_pillars, periphery_pillars = get_core_periphery_pillars()
    core_sims, periphery_sims, border_sims = get_core_periphery_values_by_similarity(core_pillars, periphery_pillars,
                                                                                     nbrs_sim_dict)

    core_avg_sim = np.mean(core_sims)
    periphery_avg_sim = np.mean(periphery_sims)

    observed_diff = core_avg_sim - periphery_avg_sim

    # Initialize an array to store permuted test statistics
    permuted_diffs = np.zeros(num_permutations)
    for i in range(num_permutations):
        random_G = build_pillars_graph(shuffle_ts=True, draw=False)
        random_ns, random_strong_nodes, _ = nodes_strengths(random_G, draw=False)
        random_sim_dict = nbrs_nodes_similarity_by_strength(random_G, random_ns)
        random_core_pillars, random_periphery_pillars = get_core_periphery_pillars()
        random_core_sims, random_periphery_sims, random_border_sims = get_core_periphery_values_by_similarity(
            random_core_pillars,
            random_periphery_pillars,
            random_sim_dict)
        random_core_avg_sim = np.mean(random_core_sims)
        random_periphery_avg_sim = np.mean(random_periphery_sims)
        permuted_diff = random_core_avg_sim - random_periphery_avg_sim
        permuted_diffs[i] = (permuted_diff)

        # Calculate the p-value
    p_value = np.sum(permuted_diffs >= observed_diff) / num_permutations
    if p_value < alpha:
        print("Reject the null hypothesis. The original values are statistically significant.")
    else:
        print("Fail to reject the null hypothesis.")

    return observed_diff, permuted_diffs, p_value


def build_pillars_similarity_graph(G, nbrs_similarity_dict):
    for pair, sim in nbrs_similarity_dict.items():
        node1_idx = next((i for i, p in G.nodes(data=True) if p.get('pos') == pair[0]), None)
        node2_idx = next((i for i, p in G.nodes(data=True) if p.get('pos') == pair[1]), None)
        G[node1_idx][node2_idx]['weight'] = sim[1]

    img = get_last_image_whiten(build_image=Consts.build_image)
    fig, ax = plt.subplots()
    ax.imshow(img, cmap='gray')

    pos = nx.get_node_attributes(G, 'pos')
    nodes_loc_y_inverse = {k: (v[1], v[0]) for k, v in pos.items()}

    edges, weights = zip(*nx.get_edge_attributes(G, 'weight').items())

    nx.draw(G, nodes_loc_y_inverse, edgelist=edges, edge_color=weights,
            width=3.0, node_size=50)

    sm = plt.cm.ScalarMappable()
    sm.set_array(weights)
    plt.colorbar(sm)

    if Consts.SHOW_GRAPH:
        plt.show()

    return G


def get_pillars_edges_over_avg_similarity(nbrs_similarity_dict):
    all_sims = [v[1] for v in nbrs_similarity_dict.values()]
    avg_sim = np.sum(all_sims) / len(all_sims)

    pillars_pair_to_sim_abov_avg = {}
    for k, v in nbrs_similarity_dict.items():
        if v[1] > avg_sim:
            pillars_pair_to_sim_abov_avg[k] = v[1]

    return pillars_pair_to_sim_abov_avg


def test_avg_similarity_significance(num_permutations=1000, alpha=0.05):
    G = build_pillars_graph(random_neighbors=False, shuffle_ts=False, draw=False)
    ns, strong_nodes, _ = nodes_strengths(G, draw=False)
    sim_dict = nbrs_nodes_similarity_by_strength(G, ns)
    vals = sim_dict.values()
    sim = [v[1] for v in vals]
    avg_sim = np.mean(sim)

    # Initialize an array to store permuted test statistics
    permuted_test_statistics = np.zeros(num_permutations)
    for i in range(num_permutations):
        random_G = build_pillars_graph(random_neighbors=False, shuffle_ts=True, draw=False)
        random_ns, random_strong_nodes, _ = nodes_strengths(random_G, draw=False)
        random_sim_dict = nbrs_nodes_similarity_by_strength(random_G, random_ns)
        random_vals = random_sim_dict.values()
        random_sim = [v[1] for v in random_vals]
        random_avg_sim = np.mean(random_sim)
        permuted_test_statistics[i] = random_avg_sim

    # Calculate the p-value
    p_value = np.sum(permuted_test_statistics >= avg_sim) / num_permutations
    if p_value < alpha:
        print("Reject the null hypothesis. The original values are statistically significant.")
    else:
        print("Fail to reject the null hypothesis.")

    return avg_sim, permuted_test_statistics, p_value


def strong_nodes_avg_distance_from_center(G, alive_centers, strong_nodes, all_nodes_strength=None, removed_nodes=None,
                                          draw=False):
    central_point = (np.mean([x[0] for x in alive_centers]), np.mean([x[1] for x in alive_centers]))

    # Calculate distances and average distance
    distances = []
    for node_idx in all_nodes_strength:
        x, y = G.nodes[node_idx]['pos']
        distance = math.sqrt((x - central_point[0]) ** 2 + (y - central_point[1]) ** 2)
        distances.append(distance)

    normalized_distances = np.array(distances) / max(distances)
    strong_nodes_distances = [normalized_distances[i] for i in strong_nodes]
    average_distance = sum(strong_nodes_distances) / len(strong_nodes_distances)

    if draw:
        # Plot the distribution of distances
        plt.hist(distances, bins=10, edgecolor='black')
        plt.xlabel('Distance')
        plt.ylabel('Frequency')
        plt.title('Distribution of Distances')

        # Show the plot
        plt.show()

    return strong_nodes_distances, average_distance


def strong_nodes_avg_distance_from_center_by_hops(G, alive_centers, strong_nodes, removed_nodes=None):
    central_point = (np.mean([x[0] for x in alive_centers]), np.mean([x[1] for x in alive_centers]))
    centers = nx.center(G)

    full_G = G.copy()
    for i in removed_nodes:
        full_G.add_node(i[0], pos=i[1]['pos'])

    # Calculate the distance from each center node to the central position
    distances_to_central_position = {}
    for center_node in centers:
        center_node_position = full_G.nodes[center_node]['pos']
        distance = ((center_node_position[0] - central_point[0]) ** 2 +
                    (center_node_position[1] - central_point[1]) ** 2) ** 0.5
        distances_to_central_position[center_node] = distance

    # Find the center node with the shortest distance to the central position
    closest_center_node = min(distances_to_central_position, key=distances_to_central_position.get)

    # full_G.add_nodes_from(removed_nodes)
    total_dists = []
    for node in full_G.nodes():
        if node in removed_nodes:
            total_dists.append(0)
            continue
        distance = nx.shortest_path_length(full_G, source=closest_center_node, target=node)
        total_dists.append(distance)

    normalized_distances = np.array(total_dists) / max(total_dists)
    strong_nodes_distances = [normalized_distances[i] for i in strong_nodes]
    average_distance = sum(strong_nodes_distances) / len(strong_nodes_distances)

    return average_distance


def strong_nodes_avg_distance_from_center_in_different_distance_categories(G, alive_centers, strong_nodes, draw=False,
                                                                           removed_nodes=None):
    central_point = (np.mean([x[0] for x in alive_centers]), np.mean([x[1] for x in alive_centers]))
    centers = nx.center(G)

    # full_G = G.copy()
    # for i in removed_nodes:
    #     full_G.add_node(i[0], pos=i[1]['pos'])

    # Calculate the distance from each center node to the central position
    distances_to_central_position = {}
    for center_node in centers:
        center_node_position = G.nodes[center_node]['pos']
        distance = ((center_node_position[0] - central_point[0]) ** 2 +
                    (center_node_position[1] - central_point[1]) ** 2) ** 0.5
        distances_to_central_position[center_node] = distance

    # Find the center node with the shortest distance to the central position
    closest_center_node = min(distances_to_central_position, key=distances_to_central_position.get)

    strong_node_distances = {}

    # Calculate distances for each strong node from the center
    for strong_node in strong_nodes:
        distance = nx.shortest_path_length(G, source=closest_center_node, target=strong_node)
        strong_node_distances[strong_node] = distance

    # Initialize a dictionary to store average distances for each distance category
    distances_to_nodes = {}
    # Group nodes by distance from the center
    for node in G.nodes():
        distance = nx.shortest_path_length(G, source=closest_center_node, target=node)

        if distance in distances_to_nodes:
            distances_to_nodes[distance].append(node)
        else:
            distances_to_nodes[distance] = [node]

    # Calculate the average distance for strong nodes in each distance category
    dist_category_to_avg_strong_nodes_dist = {}
    for distance, nodes in distances_to_nodes.items():
        total_nodes_at_distance = len(nodes)
        sum_strong_node_distances = sum(strong_node_distances[node] for node in nodes if node in strong_nodes)

        if total_nodes_at_distance > 0:
            avg_distance = sum_strong_node_distances / total_nodes_at_distance
        else:
            avg_distance = 0

        dist_category_to_avg_strong_nodes_dist[distance] = avg_distance

    min_distance = min(dist_category_to_avg_strong_nodes_dist.values())
    max_distance = max(dist_category_to_avg_strong_nodes_dist.values())
    strong_nodes_avg_dist_by_hop = sum(dist_category_to_avg_strong_nodes_dist.values()) / len(
        dist_category_to_avg_strong_nodes_dist)

    normalized_average_distance = (strong_nodes_avg_dist_by_hop - min_distance) / (max_distance - min_distance)

    if draw:
        # Extract distances and average distances for plotting
        distances = list(dist_category_to_avg_strong_nodes_dist.keys())
        average_distances = list(dist_category_to_avg_strong_nodes_dist.values())

        # Create a scatter plot to visualize the relationship
        plt.bar(distances, average_distances)
        plt.xlabel("Distance from Center")
        plt.ylabel("Average Distance of Strong Nodes")
        plt.title("Average Distance of Strong Nodes vs. Distance from Center")
        plt.show()

    return normalized_average_distance


def clustering_strong_nodes_by_Louvain(G, node_strengths, strong_nodes, draw=False):
    # Create a subgraph containing only the strong nodes and their neighbors
    strong_subgraph = G.subgraph(strong_nodes)

    # Detect communities using Louvain Modularity on the strong subgraph
    strong_partition = community.best_partition(strong_subgraph)

    # Convert the partition dictionary into a list of clusters
    strong_clusters = {}
    for node, cluster_id in strong_partition.items():
        strong_clusters.setdefault(cluster_id, []).append(node)

    if draw:
        img = get_last_image_whiten(build_image=Consts.build_image)
        fig, ax = plt.subplots()
        ax.imshow(img, cmap='gray')

        pos = nx.get_node_attributes(G, 'pos')
        nodes_loc_y_inverse = {k: (v[1], v[0]) for k, v in pos.items()}

        # Draw the strong nodes with different colors for each cluster
        for cluster_id, nodes in strong_clusters.items():
            nx.draw(strong_subgraph.subgraph(nodes), nodes_loc_y_inverse, node_color=f"C{cluster_id % 10}",
                    label=f"Cluster {cluster_id}")

        # nx.draw_networkx_labels(my_G, nodes_loc_y_inverse, font_color="whitesmoke", font_size=8)

        # Draw the edges
        nx.draw_networkx_edges(G, nodes_loc_y_inverse)

        # Display the node strengths as labels
        nx.draw_networkx_labels(G, nodes_loc_y_inverse, labels=node_strengths, font_size=8)

        # Show the graph
        plt.axis('off')
        plt.show()

    return strong_clusters


def strong_nodes_connected_components(G, node_strengths, strong_nodes, draw=False):
    # Create a subgraph containing only the strong nodes and their neighbors
    strong_subgraph = G.subgraph(strong_nodes)

    strong_nodes_cc_sorted = sorted(nx.connected_components(strong_subgraph), key=len, reverse=True)
    largest_cc = max(nx.connected_components(strong_subgraph), key=len)

    if draw:
        img = get_last_image_whiten(build_image=Consts.build_image)
        fig, ax = plt.subplots()
        ax.imshow(img, cmap='gray')

        pos = nx.get_node_attributes(G, 'pos')
        nodes_loc_y_inverse = {k: (v[1], v[0]) for k, v in pos.items()}

        # Draw the strong nodes with different colors for each cluster
        for cluster_id, nodes in enumerate(strong_nodes_cc_sorted):
            nx.draw(strong_subgraph.subgraph(nodes), nodes_loc_y_inverse, node_color=f"C{cluster_id % 10}",
                    label=f"Cluster {cluster_id}")

        # Draw the edges
        nx.draw_networkx_edges(G, nodes_loc_y_inverse)
        nx.draw_networkx_labels(G, nodes_loc_y_inverse, labels=node_strengths, font_size=8)
        plt.axis('off')
        plt.show()

    return strong_nodes_cc_sorted, largest_cc


def test_strong_nodes_distance_significance(num_permutations=1000, alpha=0.05):
    G = build_pillars_graph(random_neighbors=False, shuffle_ts=False, draw=False)
    ns, strong_nodes, _ = nodes_strengths(G, draw=False)
    original_strong_nodes_avg_distance = strong_nodes_avg_distance_from_center(G,
                                                                               alive_centers=get_seen_centers_for_mask(),
                                                                               strong_nodes=strong_nodes,
                                                                               all_nodes_strength=ns, draw=False)

    # Initialize an array to store permuted test statistics
    permuted_test_statistics = np.zeros(num_permutations)
    for i in range(num_permutations):
        random_G = build_pillars_graph(random_neighbors=False, shuffle_ts=True, draw=False)
        random_ns, random_strong_nodes, _ = nodes_strengths(random_G, draw=False)
        random_strong_nodes_avg_distance = strong_nodes_avg_distance_from_center(random_G,
                                                                                 alive_centers=get_seen_centers_for_mask(),
                                                                                 strong_nodes=random_strong_nodes,
                                                                                 all_nodes_strength=random_ns,
                                                                                 draw=False)
        permuted_test_statistics[i] = random_strong_nodes_avg_distance

    # Calculate the p-value
    p_value = np.sum(permuted_test_statistics >= original_strong_nodes_avg_distance) / num_permutations
    if p_value < alpha:
        print("Reject the null hypothesis. The original values are statistically significant.")
    else:
        print("Fail to reject the null hypothesis.")

    return original_strong_nodes_avg_distance, permuted_test_statistics, p_value


def test_strong_nodes_distance_hops_significance(num_permutations=1000, alpha=0.05):
    G, removed_nodes = build_pillars_graph(random_neighbors=False, draw=False)
    ns, strong_nodes, _ = nodes_strengths(G, draw=False)
    original_strong_nodes_avg_hops = strong_nodes_avg_distance_from_center_by_hops(G,
                                                                                   alive_centers=get_seen_centers_for_mask(),
                                                                                   strong_nodes=strong_nodes,
                                                                                   removed_nodes=removed_nodes)

    # Initialize an array to store permuted test statistics
    permuted_test_statistics = np.zeros(num_permutations)
    for i in range(num_permutations):
        try:
            random_G, removed_nodes_random = build_pillars_graph(random_neighbors=True, draw=False)
            random_ns, random_strong_nodes, _ = nodes_strengths(random_G, draw=False)
            random_strong_nodes_avg_distance = strong_nodes_avg_distance_from_center_by_hops(random_G,
                                                                                             alive_centers=get_seen_centers_for_mask(),
                                                                                             strong_nodes=random_strong_nodes,
                                                                                             removed_nodes=removed_nodes_random)
            permuted_test_statistics[i] = random_strong_nodes_avg_distance
        except:
            continue

    # Calculate the p-value
    p_value = np.sum(permuted_test_statistics >= original_strong_nodes_avg_hops) / num_permutations
    if p_value < alpha:
        print("Reject the null hypothesis. The original values are statistically significant.")
    else:
        print("Fail to reject the null hypothesis.")

    return original_strong_nodes_avg_hops, permuted_test_statistics, p_value


def test_strong_nodes_number_of_cc_significance(num_permutations=1000, alpha=0.05):
    G = build_pillars_graph(random_neighbors=False, shuffle_ts=False, draw=False)
    ns, strong_nodes, _ = nodes_strengths(G, draw=False)
    strong_nodes_cc_sorted, _ = strong_nodes_connected_components(G, ns, strong_nodes, draw=False)
    num_of_cc = len(strong_nodes_cc_sorted)

    # Initialize an array to store permuted test statistics
    permuted_test_statistics = np.zeros(num_permutations)
    for i in range(num_permutations):
        random_G = build_pillars_graph(random_neighbors=False, shuffle_ts=True, draw=False)
        random_ns, random_strong_nodes, _ = nodes_strengths(random_G, draw=False)
        random_cc_dict, _ = strong_nodes_connected_components(random_G, random_ns, random_strong_nodes, draw=False)
        random_num_cc = len(random_cc_dict)
        permuted_test_statistics[i] = random_num_cc

    # Calculate the p-value
    p_value = np.sum(permuted_test_statistics <= num_of_cc) / num_permutations
    if p_value < alpha:
        print("Reject the null hypothesis. The original values are statistically significant.")
    else:
        print("Fail to reject the null hypothesis.")

    return num_of_cc, permuted_test_statistics, p_value


def test_strong_nodes_largest_cc_significance(num_permutations=1000, alpha=0.05):
    G = build_pillars_graph(random_neighbors=False, shuffle_ts=False, draw=False)
    ns, strong_nodes, _ = nodes_strengths(G, draw=False)
    _, largest_cc = strong_nodes_connected_components(G, ns, strong_nodes, draw=False)
    largest_cc_size = len(largest_cc)

    # Initialize an array to store permuted test statistics
    permuted_test_statistics = np.zeros(num_permutations)
    for i in range(num_permutations):
        random_G = build_pillars_graph(random_neighbors=False, shuffle_ts=True, draw=False)
        random_ns, random_strong_nodes, _ = nodes_strengths(random_G, draw=False)
        _, random_largest_cc = strong_nodes_connected_components(random_G, random_ns, random_strong_nodes, draw=False)
        random_largest_cc_size = len(random_largest_cc)
        permuted_test_statistics[i] = random_largest_cc_size

    # Calculate the p-value
    p_value = np.sum(permuted_test_statistics >= largest_cc_size) / num_permutations
    if p_value < alpha:
        print("Reject the null hypothesis. The original values are statistically significant.")
    else:
        print("Fail to reject the null hypothesis.")

    return largest_cc_size, permuted_test_statistics, p_value


def test_strong_nodes_clusters_louvain_significance(num_permutations=1000, alpha=0.05):
    G = build_pillars_graph(random_neighbors=False, draw=False)
    ns, strong_nodes, _ = nodes_strengths(G, draw=False)
    clusters_dict = clustering_strong_nodes_by_Louvain(G, ns, strong_nodes, draw=False)
    num_of_clusters = len(clusters_dict.keys())

    # Initialize an array to store permuted test statistics
    permuted_test_statistics = np.zeros(num_permutations)
    for i in range(num_permutations):
        random_G = build_pillars_graph(random_neighbors=True, draw=False)
        random_ns, random_strong_nodes, _ = nodes_strengths(random_G, draw=False)
        random_clusters_dict = clustering_strong_nodes_by_Louvain(random_G, random_ns, random_strong_nodes, draw=False)
        random_num_clusters = len(random_clusters_dict.keys())
        permuted_test_statistics[i] = random_num_clusters

    # Calculate the p-value
    p_value = np.sum(permuted_test_statistics <= num_of_clusters) / num_permutations
    if p_value < alpha:
        print("Reject the null hypothesis. The original values are statistically significant.")
    else:
        print("Fail to reject the null hypothesis.")

    return num_of_clusters, permuted_test_statistics, p_value


def centrality_measure_strong_nodes(G, node_strengths, strong_nodes, draw=False):
    # Create a subgraph containing only the strong nodes and their neighbors
    # strong_subgraph = G.subgraph(strong_nodes)

    # Compute centrality measures for the strong nodes subgraph
    strong_betweenness_centrality = nx.betweenness_centrality(G, weight='weight')
    strong_eigenvector_centrality = nx.eigenvector_centrality(G)

    if draw:
        img = get_last_image_whiten(build_image=Consts.build_image)
        fig, ax = plt.subplots()
        ax.imshow(img, cmap='gray')

        pos = nx.get_node_attributes(G, 'pos')

        nx.draw(G, pos, node_color=[strong_betweenness_centrality[node] for node in G.nodes()], cmap=plt.cm.Reds,
                node_size=100, font_size=8, font_color='black', alpha=0.7)

        # plt.colorbar(label="Betweenness Centrality")

        # nx.draw_networkx_labels(my_G, nodes_loc_y_inverse, font_color="whitesmoke", font_size=8)

        # Draw the edges
        nx.draw_networkx_edges(G, pos)

        # Display the node strengths as labels
        nx.draw_networkx_labels(G, pos, labels=node_strengths, font_size=12)

        # Show the graph
        plt.axis('off')
        plt.show()


def graph_communities(G):
    # Detect communities using the Louvain method
    partition = community.best_partition(G)

    # Retrieve the communities
    communities = {}
    for node, community_id in partition.items():
        if community_id not in communities:
            communities[community_id] = []
        communities[community_id].append(node)

    # Print the communities
    for community_id, nodes in communities.items():
        print(f"Community {community_id}: {nodes}")


def adf_stationary_test(pillars_time_series):
    pillars_time_series_stationary = {}
    non_stationary_pillars = []
    for p, ts in pillars_time_series.items():
        adf_test = sm.tsa.adfuller(ts, autolag='AIC')
        diff_series = pd.Series(ts)
        if adf_test[1] >= 0.05:
            for i in range(5):
                diff_series = diff_series.diff().dropna()
                adf_test = sm.tsa.adfuller(diff_series, autolag='AIC')
                if adf_test[1] < 0.05:
                    break
        if adf_test[1] >= 0.05:
            non_stationary_pillars.append(p)

        if adf_test[1] < 0.05:
            pillars_time_series_stationary[p] = diff_series
    max_possible_len = len(list(pillars_time_series.values())[0])
    for i, s in enumerate(list(pillars_time_series_stationary.values())):
        if len(s) < max_possible_len:
            max_possible_len = len(s)

    for p, ts in pillars_time_series_stationary.items():
        pillars_time_series_stationary[p] = ts[len(ts) - max_possible_len:]

    return pillars_time_series_stationary, non_stationary_pillars


def pillars_strength_by_intens_similarity_in_time(pillar_intensity_dict, pillar_to_nbrs, G, n_frames_to_avg=10,
                                                  show_strength_colormap=False, show_above_avg=False):
    def normalize_ts_by_min_max(data):
        normalized_data = {}
        for key, series in data.items():
            min_val = np.min(series)
            max_val = np.max(series)
            # Avoid division by zero in case max and min are the same
            range_val = max_val - min_val if max_val != min_val else 1
            normalized_series = (series - min_val) / range_val
            normalized_data[key] = normalized_series
        return normalized_data

    normalized_pillar_intensity_dict = normalize_ts_by_min_max(pillar_intensity_dict)

    frame_to_alive_pillars = get_alive_center_ids_by_frame_v3()
    frame_start = 0
    frame_end = len(frame_to_alive_pillars)
    alive_pillars_to_start_living_frame = {}
    for curr_frame, alive_pillars_in_frame in frame_to_alive_pillars.items():
        if frame_start <= curr_frame <= frame_end:
            for alive_pillar in alive_pillars_in_frame:
                if alive_pillar not in alive_pillars_to_start_living_frame:
                    alive_pillars_to_start_living_frame[alive_pillar] = curr_frame

    nodes_loc = get_alive_pillar_ids_overall_v3()
    nodes_loc = list(nodes_loc)
    nodes_loc_y_inverse = [(loc[1], loc[0]) for loc in nodes_loc]
    node_loc2index = {}
    for i in range(len(nodes_loc)):
        node_loc2index[str(nodes_loc[i])] = i

    pillars_pair_to_sim_dict = {}
    for frame in frame_to_alive_pillars.keys():
        for p in pillar_to_nbrs.keys():
            p1_start_frame = alive_pillars_to_start_living_frame[p]
            if p1_start_frame <= frame:
                for nbr in pillar_to_nbrs[p]:
                    p2_start_frame = alive_pillars_to_start_living_frame[nbr]
                    if p2_start_frame <= frame:
                        diff = abs(
                            normalized_pillar_intensity_dict[p][frame] - normalized_pillar_intensity_dict[nbr][frame])
                        sim = 1 - diff
                        if (p, nbr) not in pillars_pair_to_sim_dict:
                            pillars_pair_to_sim_dict[(p, nbr)] = []
                        pillars_pair_to_sim_dict[(p, nbr)].append(sim)

        if (frame + 1) % n_frames_to_avg == 0:
            pillars_pair_to_sim_dict = {k: np.mean(v) for k, v in pillars_pair_to_sim_dict.items()}
            if G.number_of_edges() > 0:
                G.remove_edges_from(list(G.edges()))
            for p, nbrs in pillar_to_nbrs.items():
                for nbr in nbrs:
                    if (p, nbr) in pillars_pair_to_sim_dict.keys():
                        G.add_edge(node_loc2index[str(p)], node_loc2index[str(nbr)])
                        G[node_loc2index[str(p)]][node_loc2index[str(nbr)]]['weight'] = pillars_pair_to_sim_dict[
                            (p, nbr)]

            node_strengths = {}
            for node in G.nodes:
                incident_edges = G.edges(node, data='weight')
                strength = sum(weight for _, _, weight in incident_edges) / len(incident_edges) if incident_edges else 0
                node_strengths[node] = round(strength, 2)

            if show_strength_colormap:
                img = get_last_image_whiten(build_image=Consts.build_image)
                fig, ax = plt.subplots()
                ax.imshow(img, cmap='gray')
                cmap = cm.get_cmap('coolwarm')
                norm = plt.Normalize(0, 1)
                node_colors = [cmap(norm(node_strengths[node])) for node in G.nodes]
                nx.draw(G, nodes_loc_y_inverse, node_color=node_colors, cmap=cmap)
                sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
                sm.set_array([])
                plt.colorbar(sm, label='Strength')
                nx.draw_networkx_edges(G, nodes_loc_y_inverse)
                nx.draw_networkx_labels(G, nodes_loc_y_inverse, labels=node_strengths, font_size=8)
                plt.axis('off')
                plt.show()
            if show_above_avg:
                avg_strength = np.percentile(list(node_strengths.values()), 80)
                # avg_strength = np.median(list(node_strengths.values()))
                node_color = ["green" if s > avg_strength else "grey" for s in node_strengths.values()]
                img = get_last_image_whiten(build_image=Consts.build_image)
                fig, ax = plt.subplots()
                ax.imshow(img, cmap='gray')
                nx.draw(G, nodes_loc_y_inverse, node_color=node_color)
                nx.draw_networkx_edges(G, nodes_loc_y_inverse)
                nx.draw_networkx_labels(G, nodes_loc_y_inverse, labels=node_strengths, font_size=8)
                plt.axis('off')
                plt.show()

            pillars_pair_to_sim_dict = {}


def get_pillar_to_intensity_for_shuffle_ts():
    # Get intensities (in timeseries)
    pillar_intens = get_pillar_to_intensity_norm_by_inner_pillar_noise()
    # Shuffle timeseries (between pillars)
    # Get a list of the dictionary values
    values = list(pillar_intens.values())

    # Shuffle the list of values in place
    random.shuffle(values)

    # Create a new dictionary with the shuffled values
    shuffled_pillar_intens = {key: value for key, value in zip(pillar_intens.keys(), values)}

    return shuffled_pillar_intens


def pillars_to_pixels():
    def find_lines_for_isolated(isolated_points, pillar_chains, tolerance=11):
        isolated_matched = []
        curr_m = 0
        for chain in pillar_chains:
            if len(chain['pillars']) >= 2:
                pillar1 = chain['pillars'][0]
                pillar2 = chain['pillars'][1]
                x1, y1 = pillar1
                x2, y2 = pillar2
                curr_m = (y2 - y1) / (x2 - x1)
                b = y1 - curr_m * x1

                for x, y in isolated_points:
                    if abs(y - (curr_m * x + b)) <= tolerance:
                        chain['pillars'].append((x, y))
                        isolated_matched.append((x, y))

        # TODO: what if isolated are on the same line themselves? need to match them together
        # add remaining isolated points as new chains
        still_isolated = [p for p in isolated_points if p not in isolated_matched]
        for p in still_isolated:
            b = p[1] - curr_m * p[0]
            pillars_chain.append({'pillars': [p], 'b': b})

    def points_on_line(points, m, b, point1, point2, tolerance=11):
        on_line = {point1, point2}

        x1, y1 = point1
        x2, y2 = point2
        x_diff = x1 - x2
        last_point = point1

        add_points(b, last_point, m, on_line, points, tolerance, x1, x_diff)
        add_points(b, last_point, m, on_line, points, tolerance, x1, x_diff, -1)

        return list(on_line)

    def add_points(b, last_point, m, on_line, points, tolerance, x1, x_diff, sign=1):
        for i in range(0, sign * 20, sign):
            potential_x = x1 + (x_diff * sign)
            potential_y = m * potential_x + b
            potential_point = closest_to_point(points, (potential_x, potential_y))
            if get_distance(potential_point, (potential_x, potential_y)) <= tolerance:
                on_line.add(potential_point)
                if last_point != potential_point:
                    x1, y1 = last_point
                    x2, y2 = potential_point
                    m = (y2 - y1) / (x2 - x1)
                    b = y1 - m * x1
                    prev_x_diff = x_diff
                    x_diff = (x1 - x2)
                    if (x_diff < 0 and prev_x_diff > 0) or (x_diff > 0 and prev_x_diff < 0):
                        x_diff *= -1
                    last_point = potential_point
                    x1, y1 = last_point
            else:
                x1 = potential_x

    img_shape = get_images(get_images_path())[0].shape
    pillars_chain = []
    all_nbrs = get_alive_pillars_to_alive_neighbors()
    pillar_ids = list(get_alive_pillar_ids_overall_v3())

    m = None
    Ms = []
    pillar_ids_to_fit_on_line = list(pillar_ids)
    isolated_points = []
    while len(pillar_ids_to_fit_on_line) > 0 and pillar_ids_to_fit_on_line != isolated_points:
        pillars_not_searched = [p for p in pillar_ids_to_fit_on_line if p not in isolated_points]
        if len(pillars_not_searched) == 0:
            break
        pillar1 = closest_to_point(pillars_not_searched, (0, 0))
        nbrs = [i for i in all_nbrs[pillar1] if i in pillar_ids_to_fit_on_line]
        if len(nbrs) == 0:
            isolated_points.append(pillar1)
            continue
        found_pillar2 = False
        if m is None:
            pillar2 = nbrs[0]
            found_pillar2 = True
        else:
            for potential_nbr in nbrs:
                x1, y1 = pillar1
                x2, y2 = potential_nbr
                potential_m = (y2 - y1) / (x2 - x1)
                if sum(abs(np.array(Ms) - potential_m) <= 0.5) > 0:
                    pillar2 = potential_nbr
                    found_pillar2 = True
                    break
        if not found_pillar2:
            isolated_points.append(pillar1)
            continue

        x1, y1 = pillar1
        x2, y2 = pillar2
        m = (y2 - y1) / (x2 - x1)
        Ms.append(m)
        b = y1 - m * x1

        pillars_on_line = points_on_line(pillar_ids_to_fit_on_line, m, b, pillar1, pillar2)
        for pc in pillars_on_line:
            if pc in pillar_ids_to_fit_on_line:
                pillar_ids_to_fit_on_line.remove(pc)
            if pc in isolated_points:
                isolated_points.remove(pc)
        pillars_chain.append({'pillars': pillars_on_line, 'b': b})

    # add pillars w/o neighbours
    find_lines_for_isolated(isolated_points, pillars_chain)

    # show_pillars_on_line(pillars_chain)

    # Re-calc avg b for all chains
    for pc in pillars_chain:
        pillars = pc['pillars']
        if len(pillars) >= 2:
            bs = []
            for p1 in pillars:
                for p2 in pillars:
                    if p1 != p2:
                        x1, y1 = p1
                        x2, y2 = p2
                        m = (y2 - y1) / (x2 - x1)
                        b = y1 - m * x1
                        bs.append(b)

            pc['b'] = np.mean(bs)

    # TODO: set on matrix, before that, sort pillars_chain lists
    for pc in pillars_chain:
        pc['pillars'].sort(key=lambda x: x[0])
    pillars_chain.sort(key=lambda x: x['b'])

    x_diffs = []
    for pc in pillars_chain:
        pillars = pc['pillars']
        for i in range(len(pillars) - 1):
            p0 = pillars[0]
            p1 = pillars[1]
            x_diffs.append(p1[0] - p0[0])
    x_diff = max(x_diffs, key=x_diffs.count)

    # TODO: make sure sorted correctly

    cols = max([len(x['pillars']) for x in pillars_chain]) * 5 + 1
    rows = len(pillars_chain) * 5 + 1
    matrix = np.zeros((cols, rows), dtype='object')

    pillars_with_gaps = []
    for pc in pillars_chain:
        curr_chain = []
        pillars = pc['pillars']
        prev_pillar = pillars[0]
        curr_chain.append(prev_pillar)

        for p in pillars[1:]:
            gaps = round((p[0] - prev_pillar[0]) / x_diff) - 1
            curr_chain.extend([0] * gaps)
            curr_chain.append(p)
            prev_pillar = p

        pillars_with_gaps.append(curr_chain)

    current_row = 0
    current_col = cols // 2
    for first_row_pillar in pillars_with_gaps[0]:
        # If gap
        if first_row_pillar == 0:
            matrix[current_row][current_col] = first_row_pillar
            current_col += 2
            continue
        else:
            matrix[current_row][current_col] = first_row_pillar
            current_col += 2

    current_row = 2
    for chain in pillars_with_gaps[1:]:
        number_of_pillars_placed_in_line = 0
        matrix_upper_raw = matrix[current_row - 2]
        pillars_in_upper_row = list(matrix_upper_raw[matrix_upper_raw != 0])
        for i, p in enumerate(chain):
            if p == 0:
                continue
            pillar_upper_row_nbrs = [n for n in all_nbrs[p] if n in pillars_in_upper_row]
            # copy the list to modify
            check_closest_nbrs = list(pillar_upper_row_nbrs)
            if len(pillar_upper_row_nbrs) < 2:
                continue
            if len(pillar_upper_row_nbrs) == 3:
                closest_nbr1 = closest_to_point(check_closest_nbrs, p)
                check_closest_nbrs.remove(closest_nbr1)
                closest_nbr2 = closest_to_point(check_closest_nbrs, p)
                check_closest_nbrs.remove(closest_nbr2)
                closest_nbr3 = closest_to_point(check_closest_nbrs, p)
                nbr1_idx = list(matrix_upper_raw).index(closest_nbr1)
                nbr2_idx = list(matrix_upper_raw).index(closest_nbr2)
                nbr3_idx = list(matrix_upper_raw).index(closest_nbr3)
                sort_idx = sorted([nbr1_idx, nbr2_idx, nbr3_idx])
                referenced_col = sort_idx[0]
            if len(pillar_upper_row_nbrs) == 2:
                closest_nbr = closest_to_point(check_closest_nbrs, p)
                nbr_idx = list(matrix_upper_raw).index(closest_nbr)
                referenced_col = nbr_idx
            matrix[current_row, referenced_col] = p
            number_of_pillars_placed_in_line += 1
            next_col = referenced_col
            if i == 0:
                for next_p in chain[i + 1:]:
                    next_col += 2
                    matrix[current_row, next_col] = next_p
                    number_of_pillars_placed_in_line += 1
            elif i == len(chain) - 1:
                for prev_p in chain[i - 1::-1]:
                    prev_col -= 2
                    matrix[current_row, prev_col] = prev_p
                    number_of_pillars_placed_in_line += 1
            else:
                for next_p in chain[i + 1:]:
                    if next_p == 0:
                        next_col += 2
                        matrix[current_row, next_col] = next_p
                        continue
                    next_col += 2
                    matrix[current_row, next_col] = next_p
                    number_of_pillars_placed_in_line += 1
                prev_col = referenced_col
                for prev_p in chain[i - 1::-1]:
                    if prev_p == 0:
                        prev_col -= 2
                        matrix[current_row, prev_col] = prev_p
                        continue
                    prev_col -= 2
                    matrix[current_row, prev_col] = prev_p
                    number_of_pillars_placed_in_line += 1
            break

        # If failed to found place in row - we need to rely on single neighbour
        if number_of_pillars_placed_in_line == 0:
            for i, p in enumerate(chain):
                if p == 0:
                    continue
                pillar_upper_row_nbrs = [n for n in all_nbrs[p] if n in pillars_in_upper_row]
                if len(pillar_upper_row_nbrs) == 1:
                    nbr_idx = list(matrix_upper_raw).index(pillar_upper_row_nbrs[0])
                    referenced_col = nbr_idx
                    # options to for the col: right, left, bottom
                    # We will check based on the line (if there is one, if there isn't - put on bottom)
                    upper_nbr = pillar_upper_row_nbrs[0]
                    if current_row < 4:
                        referenced_col = referenced_col
                    else:
                        upper_upper_left = matrix[current_row - 4, referenced_col - 2]
                        upper_upper = matrix[current_row - 4, referenced_col]
                        upper_upper_right = matrix[current_row - 4, referenced_col + 2]

                        if upper_upper_left != 0:
                            sub1 = np.subtract(upper_upper_left, upper_nbr)
                            sub2 = np.subtract(upper_nbr, p)
                            # Not equal but close enough
                            if np.allclose(sub1, sub2, atol=5):
                                referenced_col += 4
                        if upper_upper_right != 0:
                            sub1 = np.subtract(upper_upper_right, upper_nbr)
                            sub2 = np.subtract(upper_nbr, p)
                            # Not equal but close enough
                            if np.allclose(sub1, sub2, atol=5):
                                referenced_col -= 4
                        if upper_upper != 0:
                            sub1 = np.subtract(upper_upper, upper_nbr)
                            sub2 = np.subtract(upper_nbr, p)
                            # Not equal but close enough
                            if np.allclose(sub1, sub2, atol=5):
                                referenced_col = referenced_col
                    # TODO:If neither of them -> maybe the one with the 0 upper upper?

                    matrix[current_row, referenced_col] = p
                    number_of_pillars_placed_in_line += 1
                    next_col = referenced_col
                    if i == 0:
                        for next_p in chain[i + 1:]:
                            next_col += 2
                            matrix[current_row, next_col] = next_p
                            number_of_pillars_placed_in_line += 1
                    elif i == len(chain) - 1:
                        for prev_p in chain[i - 1::-1]:
                            prev_col -= 2
                            matrix[current_row, prev_col] = prev_p
                            number_of_pillars_placed_in_line += 1
                    else:
                        for next_p in chain[i + 1:]:
                            if next_p == 0:
                                next_col += 2
                                matrix[current_row, next_col] = next_p
                                continue
                            next_col += 2
                            matrix[current_row, next_col] = next_p
                            number_of_pillars_placed_in_line += 1
                        prev_col = referenced_col
                        for prev_p in chain[i - 1::-1]:
                            if prev_p == 0:
                                prev_col -= 2
                                matrix[current_row, prev_col] = prev_p
                                continue
                            prev_col -= 2
                            matrix[current_row, prev_col] = prev_p
                            number_of_pillars_placed_in_line += 1
                    break
            if number_of_pillars_placed_in_line == 0:
                raise Exception("didn't place all pillars")
        current_row += 2

    return matrix


def build_3d_pillars_pixel_matrix(matrix, shuffle_ts=False, p_to_intensity=None, channel='ts'):
    non_zero_rows = np.any(matrix != 0, axis=1)
    non_zero_cols = np.any(matrix != 0, axis=0)
    pillars_id_trimmed_matrix = matrix[non_zero_rows][:, non_zero_cols]
    # matrix_3d = np.zeros((pillars_id_trimmed_matrix.shape[0],pillars_id_trimmed_matrix.shape[1], ts_length))
    matrix_pillars = list(pillars_id_trimmed_matrix[pillars_id_trimmed_matrix != 0])

    if channel == 'ts':
        channel_length = len(list(p_to_intensity.values())[0])
        matrix_3d = np.zeros((channel_length, pillars_id_trimmed_matrix.shape[0], pillars_id_trimmed_matrix.shape[1]))
        # norm_p_to_intens = min_max_intensity_normalization(p_to_intensity)
        # norm_p_to_intens = robust_intensity_normalization(p_to_intensity)
        channel_vals = zscore_intensity_normalization(p_to_intensity)
        channel_vals = {str(k): v for k, v in channel_vals.items()}
    if channel == 'correlation':
        channel_length = get_alive_pillars_correlation().shape[0]
        matrix_3d = np.zeros((channel_length, pillars_id_trimmed_matrix.shape[0], pillars_id_trimmed_matrix.shape[1]))
        if shuffle_ts:
            channel_vals = get_correlations_df_for_mixed_ts()
        else:
            channel_vals = get_alive_pillars_correlation()

    for p in matrix_pillars:
        p_indexes = [(i, j) for i in range(pillars_id_trimmed_matrix.shape[0]) for j in
                     range(pillars_id_trimmed_matrix.shape[1]) if pillars_id_trimmed_matrix[i, j] == p]
        x, y = p_indexes[0]
        matrix_3d[:, x, y] = channel_vals[str(p)]

    return matrix_3d, pillars_id_trimmed_matrix


def show_pillars_on_line(pillars_chain):
    colors = list(mcolors.TABLEAU_COLORS)
    for i, coords in enumerate([p['pillars'] for p in pillars_chain]):
        y, x = zip(*coords)
        color = colors[i % len(colors)]
        plt.imshow(get_last_image(), cmap='gray')
        plt.scatter(x, y, color=color)
    plt.show()


# TODO: delete from here
def plot_avg_cluster_time_series(p_to_intensity, segments, pillars_id_matrix_2d, save_clusters_fig=None):
    unique_labels = np.unique(segments)
    unique_labels.sort()
    avg_segment_intnes = []
    for l in unique_labels:
        if l != 0:
            intens = []
            pillars_in_labels = pillars_id_matrix_2d[segments == l]
            for p in pillars_in_labels:
                intens.append(p_to_intensity[p])
            average_intensity_in_segment = [sum(values) / len(values) for values in zip(*intens)]
            avg_segment_intnes.append(average_intensity_in_segment)
    plt.figure(figsize=(10, 8))
    for index, intensity in enumerate(avg_segment_intnes):
        plt.plot(intensity, label=f'Segment {index + 1}')
    plt.xlabel('Index')
    plt.ylabel('Avg Intensity')
    plt.legend()
    if save_clusters_fig is not None:
        file_name = "/Superpixel_Segmentation_avg_intensity_frames_" + str(save_clusters_fig) + ".png"
        plt.savefig(Consts.RESULT_FOLDER_PATH + file_name)
        plt.close()


def superpixel_segmentation(n_segments=4, p_to_intensity=None, shuffle_ts=False, channel='ts', save_clusters_fig=None):
    matrix = pillars_to_pixels()
    matrix_3d, pillars_id_matrix_2d = build_3d_pillars_pixel_matrix(matrix, shuffle_ts=shuffle_ts,
                                                                    p_to_intensity=p_to_intensity, channel=channel)
    pillars_matrix_2d_to_mask = np.where(np.vectorize(lambda x: isinstance(x, tuple))(pillars_id_matrix_2d), 1, 0)
    mask_2d = pillars_matrix_2d_to_mask > 0

    matrix_3d_float = img_as_float(matrix_3d)
    segments = slic(matrix_3d_float, n_segments=n_segments, mask=mask_2d, channel_axis=0, slic_zero=True)

    if save_clusters_fig is not None:
        plot_avg_cluster_time_series(p_to_intensity=p_to_intensity, segments=segments,
                                     pillars_id_matrix_2d=pillars_id_matrix_2d, save_clusters_fig=save_clusters_fig)
        unique_labels = np.unique(segments)
        colors = plt.cm.jet(np.linspace(0, 1, len(unique_labels)))
        colored_image = np.zeros((*segments.shape, 3), dtype=np.float32)
        legend_patches = []
        import matplotlib.patches as mpatches
        for label, color in zip(unique_labels, colors):
            if label != 0:
                colored_image[segments == label] = color[:3]
                patch = mpatches.Patch(color=color[:3], label=f'Segment {label}')
                legend_patches.append(patch)

        plt.figure(figsize=(10, 8))
        plt.imshow(colored_image)
        plt.title("Colored SLIC Superpixel Segmentation by " + channel)
        plt.legend(handles=legend_patches, bbox_to_anchor=(1.05, 1), loc='upper left', borderaxespad=0.)
        plt.tight_layout()
        plt.axis('off')
        file_name = "/Superpixel_Segmentation_by_" + channel + "_" + str(save_clusters_fig) + ".png"
        plt.savefig(Consts.RESULT_FOLDER_PATH + file_name)
        plt.close()
    # plt.show()

    return segments, matrix_3d, pillars_id_matrix_2d


def segmentation_accuracy(segments, matrix_3d):
    labels = [l for l in list(np.unique(segments)) if l != 0]
    pillars_corrs_df = get_alive_pillars_symmetric_correlation()
    p_to_intens = get_pillar_to_intensity_norm_by_inner_pillar_noise()
    correlations = {}
    intra_class_variability = []
    intra_class_dtw_distances = []
    intra_class_vec_dist = []
    # intra_class_variability = {}
    for segment_id in labels:
        seg_intens = matrix_3d[:, segments == segment_id]
        # Calculate intra-class variability (variance)
        intra_variability = np.var(seg_intens, ddof=1)
        # intra_class_variability[segment_id] = intra_variability
        intra_class_variability.append(intra_variability)
        indices = list(zip(np.where(segments == segment_id)[0], np.where(segments == segment_id)[1]))
        # Calculate DTW distances between all pairs of the same segment
        dtw_distances = []
        for idx1 in indices:
            for idx2 in indices:
                if idx1 != idx2:
                    intensity1 = matrix_3d[:, idx1[0], idx1[1]]
                    intensity2 = matrix_3d[:, idx2[0], idx2[1]]
                    dtw_distance, _ = fastdtw(intensity1, intensity2)

                    dtw_distances.append(dtw_distance)
        if len(dtw_distances) > 0:
            intra_class_dtw_distances.append(np.mean(dtw_distances))
        # Calculate distance between all pairs of the same segment
        vec_distances = []
        for idx1 in indices:
            for idx2 in indices:
                if idx1 != idx2:
                    intensity1 = matrix_3d[:, idx1[0], idx1[1]]
                    intensity2 = matrix_3d[:, idx2[0], idx2[1]]
                    vec_dist = np.linalg.norm(intensity1 - intensity2)

                    vec_distances.append(vec_dist)
        if len(vec_distances) > 0:
            intra_class_vec_dist.append(np.mean(vec_distances))
    intra_class_variability = np.mean(intra_class_variability)
    overall_intra_class_dtw_distance = np.mean(intra_class_dtw_distances)
    overall_intra_class_vec_dist = np.mean(intra_class_vec_dist)

    inter_class_dtw_distances = []
    inter_class_vec_dist = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            label1 = labels[i]
            label2 = labels[j]
            # Get indices of segments belonging to class label1 and class label2
            indices1 = list(zip(np.where(segments == label1)[0], np.where(segments == label1)[1]))
            indices2 = list(zip(np.where(segments == label2)[0], np.where(segments == label2)[1]))
            # Calculate DTW distances between all pairs of segments from different classes
            dtw_distances = []
            for idx1 in indices1:
                for idx2 in indices2:
                    intensity1 = matrix_3d[:, idx1[0], idx1[1]]
                    intensity2 = matrix_3d[:, idx2[0], idx2[1]]
                    distance, _ = fastdtw(intensity1, intensity2)
                    dtw_distances.append(distance)
            # Calculate the average DTW distance between segments of different classes
            inter_class_dtw_distances.append(np.mean(dtw_distances))
            # Calculate similarity between all pairs of segments from different classes
            vec_dists = []
            for idx1 in indices1:
                for idx2 in indices2:
                    intensity1 = matrix_3d[:, idx1[0], idx1[1]]
                    intensity2 = matrix_3d[:, idx2[0], idx2[1]]
                    dist = np.linalg.norm(intensity1 - intensity2)
                    vec_dists.append(dist)
            inter_class_vec_dist.append(np.mean(vec_dists))
    # Calculate the overall inter-class variability as the mean of all inter-class distances
    overall_inter_class_dtw_distance = np.mean(inter_class_dtw_distances)
    overall_inter_class_vec_dist = np.mean(inter_class_vec_dist)

    return intra_class_variability, overall_intra_class_dtw_distance, overall_intra_class_vec_dist, overall_inter_class_dtw_distance, overall_inter_class_vec_dist


def superpixel_segmentation_evaluation(number_of_segmentations, p_to_intensity=None, shuffle_ts=False, channel='ts',
                                       save_clusters_fig=None):
    intra_variance = {}
    intra_dtw_distance = {}
    intra_vector_distance = {}
    inter_dtw_distance = {}
    inter_vector_distance = {}
    for n in number_of_segmentations:
        segments, matrix_3d, _ = superpixel_segmentation(n_segments=n, p_to_intensity=p_to_intensity,
                                                         shuffle_ts=shuffle_ts, channel=channel,
                                                         save_clusters_fig=save_clusters_fig)
        intra_class_variability, overall_intra_class_dtw_distance, overall_intra_class_vec_dist, \
        overall_inter_class_dtw_distance, overall_inter_class_vec_dist = segmentation_accuracy(segments, matrix_3d)
        intra_variance[n] = intra_class_variability
        intra_dtw_distance[n] = overall_intra_class_dtw_distance
        intra_vector_distance[n] = overall_intra_class_vec_dist
        inter_dtw_distance[n] = overall_inter_class_dtw_distance
        inter_vector_distance[n] = overall_inter_class_vec_dist
    # lowest_intra_n = min(intra_variance, key=intra_variance.get)
    # lowest_intra_dist_n = min(intra_dtw_distance, key=intra_dtw_distance.get)
    # highest_inter_n = max(inter_dtw_distance, key=inter_dtw_distance.get)
    # print("intra similarity:", intra_similarity)
    # print("intra distance:", intra_distance)
    # print("inter dissimilarity:", inter_dissimilarity)
    # print("lowest_intra_n", lowest_intra_n)
    # print("lowest_intra_dist_n", lowest_intra_dist_n)
    # print("highest_inter_dist_n", highest_inter_n)

    return intra_variance, intra_dtw_distance, intra_vector_distance, inter_dtw_distance, inter_vector_distance


def dfs_pillar_pixel_build(pillars_loc, alive_generated_center_ids, graph, vertex_generated_id, dense_matrix,
                           curr_matrix_loc, visited=None):
    if visited is None:
        visited = set()
    visited.add(vertex_generated_id)

    vertex_center_loc = closest_to_point(pillars_loc, vertex_generated_id)

    for neighbor_loc in graph[vertex_center_loc]:
        neighbor_generated_id = closest_to_point(alive_generated_center_ids, neighbor_loc)
        if neighbor_generated_id not in visited:
            angle = (degrees(atan2(neighbor_generated_id[0] - vertex_generated_id[0],
                                   neighbor_generated_id[1] - vertex_generated_id[1])) + 90 + 360) % 360
            # right up
            if 22.5 <= angle < 67.5:
                curr_matrix_loc = (curr_matrix_loc[0] - 1, curr_matrix_loc[1] + 1)
            # right
            elif 67.5 <= angle < 112.5:
                curr_matrix_loc = (curr_matrix_loc[0], curr_matrix_loc[1] + 2)
            # right down
            elif 112.5 <= angle < 157.5:
                curr_matrix_loc = (curr_matrix_loc[0] + 1, curr_matrix_loc[1] + 1)
            # Down
            elif 157.5 <= angle < 202.5:
                curr_matrix_loc = (curr_matrix_loc[0] + 2, curr_matrix_loc[1])
            # Left down
            elif 202.5 <= angle < 247.5:
                curr_matrix_loc = (curr_matrix_loc[0] + 1, curr_matrix_loc[1] - 1)
            # Left
            elif 247.5 <= angle < 292.5:
                curr_matrix_loc = (curr_matrix_loc[0], curr_matrix_loc[1] - 2)
            # Left up
            elif 292.5 <= angle < 337.5:
                curr_matrix_loc = (curr_matrix_loc[0] - 1, curr_matrix_loc[1] - 1)
            # Up
            else:
                curr_matrix_loc = (curr_matrix_loc[0] - 2, curr_matrix_loc[1])

            # Put 2 pillars in the same location
            if dense_matrix[curr_matrix_loc[0]][curr_matrix_loc[1]] != None:
                temp = [dense_matrix[curr_matrix_loc[0]][curr_matrix_loc[1]]]
                temp.append(neighbor_generated_id)
                dense_matrix[curr_matrix_loc[0]][curr_matrix_loc[1]] = temp
            else:
                dense_matrix[curr_matrix_loc[0]][curr_matrix_loc[1]] = neighbor_generated_id

            dfs_pillar_pixel_build(pillars_loc, alive_generated_center_ids, graph, neighbor_generated_id, dense_matrix,
                                   curr_matrix_loc, visited)


def add_points_in_rule(covered_pillars, line, max_col, max_row, pillar_id, pillar_ids, rule1):
    current_loc = pillar_id
    while not is_out_of_bounds(current_loc, max_row, max_col):
        current_loc = (current_loc[0] + rule1[0], current_loc[1] + rule1[0])
        closest_id = closest_to_point(pillar_ids, current_loc)
        if closest_id is not None and np.linalg.norm(
                np.array(current_loc) - np.array(closest_id)) <= Consts.MAX_DISTANCE_PILLAR_FIXED * 1.5:
            if closest_id not in covered_pillars:
                line.append(closest_id)
                covered_pillars.add(closest_id)


def is_out_of_bounds(loc, max_row, max_col):
    return loc[0] < 0 or loc[1] < 0 or loc[0] >= max_row or loc[1] >= max_col


def calc_angle(lineA, lineB):
    line1Y1 = lineA[0][1]
    line1X1 = lineA[0][0]
    line1Y2 = lineA[1][1]
    line1X2 = lineA[1][0]

    line2Y1 = lineB[0][1]
    line2X1 = lineB[0][0]
    line2Y2 = lineB[1][1]
    line2X2 = lineB[1][0]

    # calculate angle between pairs of lines
    angle1 = math.atan2(line1Y1 - line1Y2, line1X1 - line1X2)
    angle2 = math.atan2(line2Y1 - line2Y2, line2X1 - line2X2)
    angleDegrees = (angle1 - angle2) * 360 / (2 * math.pi)
    return angleDegrees


def build_graph(random_neighbors=False, shuffle_ts=False, draw=False):
    def normalize_values(values_dict):
        min_value = min(values_dict.values())
        max_value = max(values_dict.values())
        for k, v in values_dict.items():
            norm_value = (v - min_value) / (max_value - min_value)
            values_dict[k] = norm_value

        return values_dict

    G = nx.Graph()
    p_to_intens = get_pillar_to_intensity_norm_by_inner_pillar_noise()
    min_max_scaler = MinMaxScaler()
    normalized_p_to_intens = {key: min_max_scaler.fit_transform(np.array(value).reshape(-1, 1)).flatten() for
                              key, value in p_to_intens.items()}
    nodes_loc = get_alive_pillar_ids_overall_v3()
    nodes_loc = list(nodes_loc)
    nodes_loc_y_inverse = [(loc[1], loc[0]) for loc in nodes_loc]
    node_loc2index = {}
    for i in range(len(nodes_loc)):
        node_loc2index[str(nodes_loc[i])] = i
        G.add_node(i, pos=nodes_loc[i], intensity=normalized_p_to_intens[nodes_loc[i]])
        # G.add_node(i, pos=nodes_loc[i])

    if random_neighbors:
        neighbors = get_random_neighbors()
    else:
        neighbors = get_alive_pillars_to_alive_neighbors()

    if Consts.only_alive:
        correlation = get_alive_pillars_symmetric_correlation()
    else:
        correlation = get_all_pillars_correlations()

    if shuffle_ts:
        correlation = get_correlations_df_for_mixed_ts()

    pillars_pair_to_corr = {}
    for pillar, nbrs in neighbors.items():
        for nbr in nbrs:
            if (pillar, nbr) not in pillars_pair_to_corr and (nbr, pillar) not in pillars_pair_to_corr:
                if str(nbr) in correlation and str(pillar) in correlation and not np.isnan(
                        correlation[str(pillar)][str(nbr)]):
                    pillars_pair_to_corr[(pillar, nbr)] = (correlation[str(pillar)][str(nbr)])

    pillars_pair_to_corr = normalize_values(pillars_pair_to_corr)

    for pair, corr in pillars_pair_to_corr.items():
        G.add_edge(node_loc2index[str(pair[0])], node_loc2index[str(pair[1])])
        G[node_loc2index[str(pair[0])]][node_loc2index[str(pair[1])]]['weight'] = corr

    if draw:
        if nx.get_edge_attributes(G, 'weight') == {}:
            return
        edges, weights = zip(*nx.get_edge_attributes(G, 'weight').items())
        img = get_last_image_whiten(build_image=Consts.build_image)
        fig, ax = plt.subplots()
        ax.imshow(img, cmap='gray')
        nx.draw(G, nodes_loc_y_inverse, edgelist=edges, edge_color=weights,
                width=3.0, node_size=50)
        sm = plt.cm.ScalarMappable()
        sm.set_array(weights)
        plt.colorbar(sm)
        if Consts.SHOW_GRAPH:
            plt.show()

    return G


def louvain_cluster_nodes(G, draw=False):
    partition = community.best_partition(G, resolution=1.05, random_state=42)

    # Convert the partition dictionary into a list of clusters
    clusters = {}
    for node, cluster_id in partition.items():
        clusters.setdefault(cluster_id, []).append(node)

    if draw:
        img = get_last_image_whiten(build_image=Consts.build_image)
        fig, ax = plt.subplots()
        ax.imshow(img, cmap='gray')

        pos = nx.get_node_attributes(G, 'pos')
        nodes_loc_y_inverse = {k: (v[1], v[0]) for k, v in pos.items()}
        for cluster_id, nodes in clusters.items():
            nx.draw(G.subgraph(nodes), nodes_loc_y_inverse, node_color=f"C{cluster_id % 10}",
                    label=f"Cluster {cluster_id}")
        nx.draw_networkx_edges(G, nodes_loc_y_inverse)
        plt.axis('off')
        plt.show()


def build_fully_connected_graph(random_neighbors=False, shuffle_ts=False, draw=False):
    G = nx.Graph()
    p_to_intens = get_pillar_to_intensity_norm_by_inner_pillar_noise()
    min_max_scaler = MinMaxScaler()
    normalized_p_to_intens_series = {}
    for key, value in p_to_intens.items():
        normalized_values = min_max_scaler.fit_transform(np.array(value).reshape(-1, 1)).flatten()
        time_index = pd.RangeIndex(start=0, stop=len(normalized_values), step=1)
        series = pd.Series(normalized_values, index=time_index)
        normalized_p_to_intens_series[key] = series
    nodes_loc = get_alive_pillar_ids_overall_v3()
    nodes_loc = list(nodes_loc)
    nodes_loc_y_inverse = [(loc[1], loc[0]) for loc in nodes_loc]
    node_loc2index = {}
    for i in range(len(nodes_loc)):
        node_loc2index[str(nodes_loc[i])] = i
        G.add_node(i, pos=nodes_loc[i], intensity=normalized_p_to_intens_series[nodes_loc[i]])

    if Consts.only_alive:
        correlation = get_alive_pillars_symmetric_correlation()
    else:
        correlation = get_all_pillars_correlations()

    if shuffle_ts:
        correlation = get_correlations_df_for_mixed_ts()
    alpha = 0.2
    pillars = list(correlation.columns)
    for p1 in pillars:
        for p2 in pillars:
            if p1 != p2:
                abs_corr = abs(correlation[p1][p2])
                dist = 1 / (euclidean(eval(p1), eval(p2)))
                # f_weight = abs_corr * (1 - dist)
                # f_weight = alpha * abs_corr + (1-alpha) * (1 - dist)
                f_weight = abs(correlation[p1][p2])
                G.add_edge(node_loc2index[p1], node_loc2index[p2])
                G[node_loc2index[p1]][node_loc2index[p2]]['weight'] = f_weight

    if draw:
        if nx.get_edge_attributes(G, 'weight') == {}:
            return
        edges, weights = zip(*nx.get_edge_attributes(G, 'weight').items())
        img = get_last_image_whiten(build_image=Consts.build_image)
        fig, ax = plt.subplots()
        ax.imshow(img, cmap='gray')
        nx.draw(G, nodes_loc_y_inverse, edgelist=edges, edge_color=weights,
                width=3.0, node_size=50)
        sm = plt.cm.ScalarMappable()
        sm.set_array(weights)
        plt.colorbar(sm)
        if Consts.SHOW_GRAPH:
            plt.show()

    return G


def gcn(G):
    node_features = np.array([G.nodes[node]['intensity'] for node in G.nodes()])
    node_features = node_features.reshape(G.number_of_nodes(), node_features.shape[1])
    n_components = 2
    pca = PCA(n_components=n_components)
    reduced_features = pca.fit_transform(node_features)

    edge_index = torch.tensor(list(G.edges()), dtype=torch.long).t().contiguous()
    edge_weights = torch.tensor([G[u][v]['weight'] for u, v in G.edges()], dtype=torch.float)
    x = torch.tensor(reduced_features, dtype=torch.float)
    data = Data(x=x, edge_index=edge_index, edge_attr=edge_weights)

    model = GCN(num_features=data.num_features, hidden_channels=12)
    optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
    for epoch in range(200):
        model.train()
        optimizer.zero_grad()
        out = model(data.x, data.edge_index)
        # Compute the loss and gradients
        # loss.backward()
        optimizer.step()

    # Generate embeddings
    model.eval()
    with torch.no_grad():
        embeddings = model(data.x, data.edge_index)
    embeddings_np = embeddings.detach().cpu().numpy()
    scaler = MinMaxScaler()
    embeddings_normalized = scaler.fit_transform(embeddings_np)

    from sklearn.neighbors import NearestNeighbors
    neigh = NearestNeighbors(n_neighbors=2)
    nbrs = neigh.fit(embeddings_normalized)
    distances, indices = nbrs.kneighbors(embeddings_normalized)
    distances = np.sort(distances, axis=0)
    distances = distances[:, 1]
    plt.figure(figsize=(20, 10))
    plt.plot(distances)
    plt.title('K-distance Graph', fontsize=20)
    plt.xlabel('Data Points sorted by distance', fontsize=14)
    plt.ylabel('Epsilon', fontsize=14)
    plt.show()

    dbscan = DBSCAN(eps=0.2, min_samples=4).fit(embeddings_normalized)
    community_assignments = dbscan.labels_

    def get_connected_components(subgraph):
        return [list(c) for c in nx.connected_components(subgraph)]

    # Adjusting clusters
    new_community_assignments = community_assignments.copy()
    for cluster_id in set(community_assignments):
        if cluster_id == -1:
            # Skip processing for noise points
            continue
        # Get nodes in the current cluster
        cluster_nodes = [i for i, label in enumerate(community_assignments) if label == cluster_id]
        # Create subgraph from the nodes in the cluster
        cluster_subgraph = G.subgraph(cluster_nodes)
        # Check if the subgraph is connected
        if not nx.is_connected(cluster_subgraph):
            # If not connected, split the cluster into connected components
            connected_components = get_connected_components(cluster_subgraph)
            # Assign new cluster IDs to each connected component (except the first one)
            for component_id, component in enumerate(connected_components[1:],
                                                     start=len(set(new_community_assignments))):
                for node in component:
                    new_community_assignments[node] = component_id
    # Update community assignments
    community_assignments = new_community_assignments

    unique_labels = set(community_assignments)
    colors = [plt.cm.jet(float(i) / max(unique_labels)) for i in unique_labels]
    color_map = [colors[label] if label >= 0 else (1, 1, 1, 1) for label in community_assignments]  # White for outliers
    if nx.get_edge_attributes(G, 'weight') == {}:
        return
    edges, weights = zip(*nx.get_edge_attributes(G, 'weight').items())
    img = get_last_image_whiten(build_image=Consts.build_image)
    fig, ax = plt.subplots()
    ax.imshow(img, cmap='gray')
    nodes_loc = get_alive_pillar_ids_overall_v3()
    nodes_loc = list(nodes_loc)
    nodes_loc_y_inverse = [(loc[1], loc[0]) for loc in nodes_loc]
    nx.draw(G, nodes_loc_y_inverse, edgelist=edges, node_size=60, node_color=color_map)  # Add node_color here
    sm = plt.cm.ScalarMappable()
    sm.set_array(weights)
    plt.colorbar(sm)
    if Consts.SHOW_GRAPH:
        plt.show()


def leave_one_out(p_to_intns, exp_name, exp_type):
    data_df = pd.DataFrame()
    id_to_intns = {exp_name + str(k): v for k, v in p_to_intns.items()}
    df = pd.DataFrame(id_to_intns.items(), columns=['id', 'time_series'])
    type_series = pd.Series([exp_type] * len(df))
    df['type'] = type_series
    time_series_expanded = df['time_series'].apply(pd.Series)
    time_series_expanded.columns = [str(i) for i in time_series_expanded.columns]
    result_df = pd.concat([df.drop('time_series', axis=1), time_series_expanded], axis=1)
    df_long = result_df.drop('type', axis=1).melt(id_vars=['id'], var_name='time', value_name='value')
    df_long['time'] = pd.to_numeric(df_long['time'])


def df_for_tsne(p_to_intns, exp_name, exp_type, core=None, periph=None, blebb=None, ts_features=False):
    data_df = pd.DataFrame()
    id_to_intns = {exp_name + str(k): v for k, v in p_to_intns.items()}
    df = pd.DataFrame(id_to_intns.items(), columns=['id', 'time_series'])
    type_series = pd.Series([exp_type] * len(df))
    df['type'] = type_series
    if core is not None and periph is not None:
        for i, p in enumerate(list(p_to_intns.keys())):
            if p in core:
                df.loc[i, 'loc'] = 'core'
            if p in periph:
                df.loc[i, 'loc'] = 'periphery'
    if blebb is not None:
        for i, p in enumerate(list(p_to_intns.keys())):
            df.loc[i, 'blebb'] = blebb
    time_series_expanded = df['time_series'].apply(pd.Series)
    time_series_expanded.columns = [str(i) for i in time_series_expanded.columns]
    result_df = pd.concat([df.drop('time_series', axis=1), time_series_expanded], axis=1)
    if core is not None and periph is not None:
        X = result_df.drop(['id', 'type', 'loc'], axis=1)
    elif blebb is not None:
        X = result_df.drop(['id', 'type', 'blebb'], axis=1)
    else:
        X = result_df.drop(['id', 'type'], axis=1)
    if ts_features:
        X = extract_ts_features(X)
    # feature_list = X.apply(lambda row: extract_ts_features(row), axis=1)
    # X_features = pd.DataFrame(feature_list.tolist())
    df = pd.concat([df.drop(['time_series'], axis=1), X], axis=1)
    # df['id'] = exp_name
    # df = df.groupby(['id', 'type'], as_index=False).mean()
    data_df = pd.concat([data_df, df], axis=0)
    data_df.reset_index(drop=True, inplace=True)
    return data_df


def extract_ts_features(ts_df):
    df = pd.DataFrame(
        columns=['mean', 'median', 'std_dev', 'variance', 'skewness', 'kurtosis', 'quantile_25', 'quantile_50',
                 'quantile_75'])
    for i, ts in ts_df.iterrows():
        df.loc[i] = [
            ts.mean(),
            ts.median(),
            ts.std(),
            ts.var(),
            ts.skew(),
            ts.kurtosis(),
            ts.quantile(0.25),
            ts.quantile(0.5),
            ts.quantile(0.75)
        ]

    return df


def time_series_tsne_for_type(all_data_df):
    X = all_data_df.drop(['id', 'type'], axis=1)
    y = all_data_df['type'].astype('category')
    all_data_df['type'] = all_data_df['type'].astype('category')
    color_map = {'13.2': 'tab:orange', '5.3': 'tab:blue'}
    all_data_df['color'] = all_data_df['type'].map(color_map)

    # tsne = TSNE(n_components=2, perplexity=30, learning_rate=200, n_iter=1000, random_state=42)
    # X_tsne = tsne.fit_transform(X)
    # all_data_df['tsne-2d-one'] = X_tsne[:, 0]
    # all_data_df['tsne-2d-two'] = X_tsne[:, 1]

    pca = PCA(n_components=2, random_state=42)
    X_pca = pca.fit_transform(X)
    all_data_df['pca-2d-one'] = X_pca[:, 0]
    all_data_df['pca-2d-two'] = X_pca[:, 1]

    g = sns.jointplot(
        data=all_data_df,
        x='pca-2d-one',
        y='pca-2d-two',
        hue='type',
        palette=color_map,
        marginal_kws=dict(shade=True),
        alpha=0.1
    )
    g.set_axis_labels('First PCA component', 'Second PCA component')
    g.fig.subplots_adjust(top=0.9)
    # g.add_legend(title='Type')
    plt.show()


def time_series_tsne_for_location(all_data_df):
    X = all_data_df.drop(['id', 'type', 'loc'], axis=1)
    y = all_data_df['loc'].astype('category')
    all_data_df['loc'] = all_data_df['loc'].astype('category')
    color_map = {'periphery': 'tab:orange', 'core': 'tab:blue'}
    all_data_df['color'] = all_data_df['loc'].map(color_map)
    tsne = TSNE(n_components=2, perplexity=30, learning_rate=200, n_iter=1000, random_state=42)
    X_tsne = tsne.fit_transform(X)
    all_data_df['tsne-2d-one'] = X_tsne[:, 0]
    all_data_df['tsne-2d-two'] = X_tsne[:, 1]

    # pca = PCA(n_components=2, random_state=42)
    # X_pca = pca.fit_transform(X)
    # all_data_df['pca-2d-one'] = X_pca[:, 0]
    # all_data_df['pca-2d-two'] = X_pca[:, 1]

    g = sns.jointplot(
        data=all_data_df,
        x='tsne-2d-one',
        y='tsne-2d-two',
        hue='loc',
        palette=color_map,
        marginal_kws=dict(shade=True),
        alpha=0.1
    )
    g.set_axis_labels('First t-SNE component', 'Second t-SNE component')
    g.fig.subplots_adjust(top=0.9)
    # g.add_legend(title='Type')
    plt.show()


def time_series_tsne_for_blebb(all_data_df):
    X = all_data_df.drop(['id', 'type', 'blebb'], axis=1)
    y = all_data_df['blebb'].astype('category')
    all_data_df['blebb'] = all_data_df['blebb'].astype('category')
    color_map = {'After blebb': 'tab:orange', 'Before blebb': 'tab:blue'}
    all_data_df['color'] = all_data_df['blebb'].map(color_map)
    tsne = TSNE(n_components=2, perplexity=30, learning_rate=200, n_iter=1000, random_state=42)
    # X_tsne = tsne.fit_transform(X)
    # all_data_df['tsne-2d-one'] = X_tsne[:, 0]
    # all_data_df['tsne-2d-two'] = X_tsne[:, 1]

    pca = PCA(n_components=2, random_state=42)
    X_pca = pca.fit_transform(X)
    all_data_df['pca-2d-one'] = X_pca[:, 0]
    all_data_df['pca-2d-two'] = X_pca[:, 1]

    g = sns.jointplot(
        data=all_data_df,
        x='pca-2d-one',
        y='pca-2d-two',
        hue='blebb',
        palette=color_map,
        marginal_kws=dict(shade=True),
        alpha=0.1
    )
    g.set_axis_labels('First t-SNE component', 'Second t-SNE component')
    g.fig.subplots_adjust(top=0.9)
    # g.add_legend(title='Type')
    plt.show()


class GCN(torch.nn.Module):
    def __init__(self, num_features, hidden_channels):
        super(GCN, self).__init__()
        self.conv1 = GCNConv(num_features, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels)
        # Add more layers if needed

    def forward(self, x, edge_index):
        x = self.conv1(x, edge_index)
        x = torch.relu(x)
        x = self.conv2(x, edge_index)
        return x

# def get_peripheral_and_center_pillars_by_frame_according_revealing_pillars():
#     frame_to_alive_pillars = get_alive_center_ids_by_frame_v2()
#     peripheral_pillars, central_pillars = get_peripheral_and_center_by_revealing_pillars()
#
#     frame_to_peripheral_center_dict = {}
#     for frame, curr_frame_alive_pillars in frame_to_alive_pillars.items():
#         frame_to_peripheral_center_dict[frame] = {}
#         peripherals = []
#         centers = []
#         for p in curr_frame_alive_pillars:
#             if p in peripheral_pillars:
#                 peripherals.append(p)
#             if p in central_pillars:
#                 centers.append(p)
#
#         frame_to_peripheral_center_dict[frame]["peripherals"] = peripherals
#         frame_to_peripheral_center_dict[frame]["centrals"] = centers
#
#     return frame_to_peripheral_center_dict


# def get_avg_correlation_pillars_intens_move_according_to_revealing_pillars_periph_vs_central():
#     frame_to_peripheral_center_dict = get_peripheral_and_center_pillars_by_frame_according_revealing_pillars_and_nbrs()
#
#     pillars_movements_dict = get_alive_centers_movements()
#     p_to_distances_dict = {}
#     for p, v_list in pillars_movements_dict.items():
#         distances = []
#         for move_dict in v_list:
#             distances.append(move_dict['distance'])
#         p_to_distances_dict[p] = distances
#     pillars_dist_movements_df = pd.DataFrame({str(k): v for k, v in p_to_distances_dict.items()})
#
#     pillar_to_intens_dict = get_alive_pillars_to_intensities()
#     pillar_intens_df = pd.DataFrame({str(k): v for k, v in pillar_to_intens_dict.items()})
#     pillar_intens_df = pillar_intens_df[:-1]
#
#     alive_p_to_frame = get_alive_pillar_to_frame()
#     periph_pillars_intens_dist_corrs = {}
#     for p in peripheral_pillars:
#         p_start_to_live = alive_p_to_frame[p]
#         intens_vec = pillar_intens_df.loc[p_start_to_live:][str(p)]
#         move_vector = pillars_dist_movements_df.loc[p_start_to_live:][str(p)]
#         if len(intens_vec) > 1 and len(move_vector) > 1:
#             p_corr = pearsonr(intens_vec, move_vector)[0]
#             periph_pillars_intens_dist_corrs[p] = p_corr
#
#     central_pillars_intens_dist_corrs = {}
#     for p in central_pillars:
#         p_start_to_live = alive_p_to_frame[p]
#         intens_vec = pillar_intens_df.loc[p_start_to_live:][str(p)]
#         move_vector = pillars_dist_movements_df.loc[p_start_to_live:][str(p)]
#         if len(intens_vec) > 1 and len(move_vector) > 1:
#             p_corr = pearsonr(intens_vec, move_vector)[0]
#             central_pillars_intens_dist_corrs[p] = p_corr
#
#     avg_periph_sync = np.nanmean(list(periph_pillars_intens_dist_corrs.values()))
#     avg_central_sync = np.nanmean(list(central_pillars_intens_dist_corrs.values()))
#
#     avg_corr_peripheral_vs_central = {
#         "peripherals": avg_periph_sync,
#         "centrals": avg_central_sync
#     }
#
#     with open(Consts.RESULT_FOLDER_PATH + "/avg_corr_peripheral_vs_central.json", 'w') as f:
#         json.dump(avg_corr_peripheral_vs_central, f)
#
#     return avg_periph_sync, avg_central_sync
