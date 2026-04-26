#################################
#Powered by Manakav
#################################
from itertools import combinations
from pathlib import Path

def parse_mt0(filepath):
    data = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            # 自动舍弃包含 failed 的序列（不区分大小写）
            if 'fail' in line.lower():
                continue
            if line.startswith('index') or line.startswith('$') or line.startswith('.') or not line:
                continue
            parts = line.split()
            if len(parts) >= 36:
                try:
                    index = int(float(parts[0]))
                    b_values = [float(parts[i]) for i in range(3, 35)]
                    data.append({'index': index, 'b': b_values})
                except (ValueError, IndexError):
                    continue
    return data

def to_binary(value, threshold=0.5):
    return 1 if value >= threshold else 0

def hamming_distance(bin_vec1, bin_vec2):
    return sum(b1 != b2 for b1, b2 in zip(bin_vec1, bin_vec2))

def element_balance(b_vector):
    ones = sum(b_vector)
    zeros = len(b_vector) - ones
    return {
        'ones': ones,
        'zeros': zeros,
        'balance_ratio': ones / len(b_vector) if len(b_vector) > 0 else 0
    }


def format_bit_string(bin_vec):
    return ''.join(str(bit) for bit in bin_vec)


def build_binary_vectors(df, threshold=0.5):
    return {
        int(row['index']): [to_binary(v, threshold=threshold) for v in row['b']]
        for row in df
    }


def zero_vector_similarity(bin_vec):
    zero_vec = [0] * len(bin_vec)
    dist = hamming_distance(bin_vec, zero_vec)
    sim = 1 - dist / len(bin_vec) if len(bin_vec) > 0 else 0.0
    return {
        'hamming_distance': dist,
        'similarity': sim,
    }

def intra_index_similarity(bin_vectors):
    results = {}
    for idx, b_vec in bin_vectors.items():
        balance = element_balance(b_vec)
        zero_sim = zero_vector_similarity(b_vec)
        results[idx] = {
            'element_balance': balance,
            'zero_similarity': zero_sim['similarity'],
            'zero_hamming_distance': zero_sim['hamming_distance'],
        }
    return results

def inter_index_similarity(bin_vectors):
    results = {}
    indices = sorted(bin_vectors.keys())
    
    for i, j in combinations(indices, 2):
        dist = hamming_distance(bin_vectors[i], bin_vectors[j])
        results[(i, j)] = {'hamming_distance': dist, 'similarity': 1 - dist / len(bin_vectors[i])}
    
    return results


def overall_inter_correlation(inter_results, vector_length):
    # 按照公式计算整组互相关性：
    # Uniqueness = 2 / (k (k - 1)) * Σ HD(R_i, R_j) / N * 100%
    if not inter_results:
        return 0.0

    pairs = len(inter_results)
    # 计算 k: 由组合数反推 k(k-1)/2 = pairs
    # 直接用索引数量更稳妥，需要提供 k 以外的推导不必要
    total_hd = sum(r['hamming_distance'] for r in inter_results.values())
    # 由于我们只有组合数，不直接使用 k 推导，这里可先计算平均归一化汉明距离。
    avg_normalized = total_hd / pairs / vector_length
    return avg_normalized * 100


def overall_inter_similarity(inter_results, vector_length):
    # 按图中公式先计算平均归一化汉明距离，再转换为平均相似度百分比。
    # AvgSimilarity(%) = (1 - Avg(HD/N)) * 100
    avg_hd_percent = overall_inter_correlation(inter_results, vector_length)
    return 100.0 - avg_hd_percent


def resolve_input_file(argv):
    # Windows 下可直接把文件拖到 .py 脚本上，路径会作为第一个参数传入。
    if len(argv) > 1:
        return Path(argv[1]).expanduser().resolve()

    default_file = Path("./R.mt0").resolve()
    if default_file.exists():
        return default_file

    # 未传参数且默认文件不存在时，弹出文件选择框。
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        selected = filedialog.askopenfilename(
            title="请选择要分析的 .mt0 文件",
            filetypes=[("MT0 文件", "*.mt0"), ("所有文件", "*.*")],
        )
        root.destroy()
        if selected:
            return Path(selected).expanduser().resolve()
    except Exception:
        pass

    return None


def pause_before_exit_if_frozen():
    # 打包为 Windows exe 后从资源管理器启动时，执行结束会立即关窗。
    # 这里仅在 frozen 场景下暂停，终端中直接运行 python 脚本不受影响。
    import sys
    if getattr(sys, 'frozen', False):
        try:
            input("\n分析完成，按回车键退出...")
        except EOFError:
            pass

def main(filepath):
    print(f"正在解析文件: {filepath}")
    df = parse_mt0(filepath)
    print(f"已加载样本数: {len(df)}\n")

    if not df:
        print("未解析到有效数据，请检查输入文件格式。")
        return {}, {}

    bin_vectors = build_binary_vectors(df, threshold=0.5)
    sorted_indices = sorted(bin_vectors.keys())

    print("=" * 60)
    print("每个 index 的 32bit 二进制序列（门限=0.5）")
    print("=" * 60)
    for idx in sorted_indices:
        print(f"Index {idx:<6}: {format_bit_string(bin_vectors[idx])}")
    
    print("=" * 60)
    print("样本内分析 (每个 index 与 32bit 全零序列的相似度百分比---均匀性)")
    print("=" * 60)
    intra_results = intra_index_similarity(bin_vectors)
    
    print(f"{'Index':<8} {'1s':<6} {'0s':<6} {'Balance':<10} {'Similarity%'}")
    print("-" * 58)
    for idx in sorted(intra_results.keys()):
        r = intra_results[idx]
        eb = r['element_balance']
        print(f"{idx:<8} {eb['ones']:<6} {eb['zeros']:<6} {eb['balance_ratio']:.4f}       {r['zero_similarity'] * 100:.2f}%")

    if intra_results:
        import math
        similarities = [r['zero_similarity'] for r in intra_results.values()]
        intra_avg_similarity = (sum(similarities) / len(similarities)) * 100
        # 仅计算标准差
        mean = sum(similarities) / len(similarities)
        stddev = math.sqrt(sum((x - mean) ** 2 for x in similarities) / len(similarities))
        print(f"\n样本内全集合平均相似度: {intra_avg_similarity:.2f}%")
        print(f"样本内全集合相似度标准差 (Std): {stddev * 100:.4f}%")
        print("（标准差 Std：越小表示各 index 的均匀性越一致，越大则均匀性差异越大。例如：Std < 5% 通常认为均匀性较好，Std > 10% 说明均匀性差异较大）")
    else:
        print("\n样本内数据不足，无法计算全集合平均相似度。")
    
    print("\n" + "=" * 60)
    print("样本间分析 (互相关性，基于汉明距离)")
    print("=" * 60)
    inter_results = inter_index_similarity(bin_vectors)
    
    distances = [(pair, r['hamming_distance'], r['similarity']) 
                 for pair, r in inter_results.items()]
    distances_sorted = sorted(distances, key=lambda x: x[1])
    
    print("\n最相似的 10 对样本 (汉明距离最低):")
    print(f"{'Index Pair':<15} {'Hamming':<10} {'Similarity'}")
    print("-" * 40)
    for pair, dist, sim in distances_sorted[:10]:
        print(f"{str(pair):<15} {dist:<10} {sim:.4f}")
    
    print("\n最不相似的 10 对样本 (汉明距离最高):")
    print(f"{'Index Pair':<15} {'Hamming':<10} {'Similarity'}")
    print("-" * 40)
    for pair, dist, sim in distances_sorted[-10:]:
        print(f"{str(pair):<15} {dist:<10} {sim:.4f}")

    vector_length = len(next(iter(bin_vectors.values()))) if bin_vectors else 0
    if inter_results and vector_length > 0:
        avg_similarity_percent = overall_inter_similarity(inter_results, vector_length)
        # 仅计算标准差
        inter_similarities = [r['similarity'] for r in inter_results.values()]
        inter_mean = sum(inter_similarities) / len(inter_similarities)
        inter_stddev = math.sqrt(sum((x - inter_mean) ** 2 for x in inter_similarities) / len(inter_similarities))
        print(f"\n样本间平均相似度(多片唯一性): {avg_similarity_percent:.2f}%")
        print(f"样本间相似度标准差 (Std): {inter_stddev * 100:.4f}%")
        print("（标准差 Std：越小表示不同 index 之间的唯一性越一致，越大则唯一性差异越大。例如：Std < 5% 通常认为唯一性较好，Std > 10% 说明唯一性差异较大）")
    else:
        print("\n样本不足，无法计算样本间平均相似度。")
    
    return intra_results, inter_results

if __name__ == "__main__":
    import sys
    exit_code = 0
    try:
        input_file = resolve_input_file(sys.argv)
        if input_file is None or not input_file.exists():
            print("未找到可用输入文件。可将 .mt0 文件直接拖到脚本上运行。")
            exit_code = 1
        else:
            main(str(input_file))
    finally:
        pause_before_exit_if_frozen()

    sys.exit(exit_code)
