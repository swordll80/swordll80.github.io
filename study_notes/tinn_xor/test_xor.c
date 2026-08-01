/* ===========================================================================
 * Tinn 示例：用反向传播训练一个小网络学会 XOR（异或）
 * ---------------------------------------------------------------------------
 * 本文件移植自 GENANN 的 example1.c，改用 Tinn 的 API 实现同一件事。
 * 它同时是 test_xor.html 的「原本」——那个网页里的 JS 是本文件加上
 * Tinn.c 核心的逐行直译，同一个种子下两边算出的数几乎完全一样。
 *
 * 【XOR 为什么是经典例子】
 *   它是「线性不可分」的：平面上无论怎么画一条直线，
 *   都无法把 (0,0)、(1,1) 与 (0,1)、(1,0) 分开。
 *
 *      右值 in[1]
 *         1 |  1        0        （方格里的数字是期望输出）
 *           |
 *         0 |  0        1
 *           +----------------- 左值 in[0]
 *              0        1
 *
 *   所以没有隐藏层的单层感知机永远学不会 XOR，必须至少有一个隐藏层——
 *   隐藏层先把输入弯到一个新空间里，在那个空间里它才变得线性可分。
 *
 * 【与 GENANN 版本的三点差异】
 *   1. GENANN 每个神经元各有一个可训练的偏置；Tinn 每层只有一个共用偏置，
 *      而且**从建网到结束一次都不更新**。这让 XOR 变得难学得多：
 *      理论上 XOR 只需 2 个隐藏神经元（一个学 OR、一个学 AND），
 *      但 OR 和 AND 需要不同的阈值，共用一个固定偏置时只能靠缩放权重去凑。
 *      实测（12 个种子）：
 *          2 个隐藏神经元 ×  500 轮 ——  0/12 成功
 *          2 个隐藏神经元 × 5000 轮 ——  1/12 成功
 *          4 个隐藏神经元 × 5000 轮 —— 11/12 成功
 *          8 个隐藏神经元 × 5000 轮 —— 12/12 成功
 *      所以本例默认用 4 个隐藏神经元、训练 3000 轮，而不是 GENANN 的 2 和 500。
 *      把 -n 调回 2 就能亲眼看到它卡在「误差降到一半就不动了」的局部极小值里。
 *   2. 权重初始化不走 Tinn 内部的 rand()，而是用本文件里的确定性 LCG
 *      覆盖一遍。这样同一个种子在任何机器、任何平台、以及网页版 JS 里
 *      都能复现出完全相同的训练过程。
 *   3. 多打印了一张 ASCII 曲面图，让你在终端里也能看到
 *      「模型学到的那张面」长什么样——网页版把它画成了真正的三维曲面。
 *
 * 【编译与运行】
 *     cmake --build <构建目录>            # 目标名 tinn_xor
 *     ./tinn_xor                          # 默认 种子3 隐藏4 学习率3 训练3000轮
 *     ./tinn_xor -s 5 -n 8 -r 1 -i 5000
 *     ./tinn_xor -n 2                     # 复现「隐藏层太小学不会」的失败案例
 *     ./tinn_xor -s 7                     # 同样参数换个种子也可能失败（局部极小值）
 * 返回值：4 个样本全对返回 0，否则返回 2（方便脚本批量统计成功率）。
 * ===========================================================================
 */

#include "Tinn.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* ---------------------------------------------------------------------------
 * 确定性随机数：线性同余发生器（LCG）
 * ---------------------------------------------------------------------------
 * 用的是 C 标准里那个最有名的 LCG 常数。之所以不用 rand()：
 * 各家 C 库的 rand() 实现不同，JavaScript 更是压根没有可播种的随机数，
 * 而本例的全部意义就在于「同一个种子 → 同一条训练轨迹」。
 * 无符号整数溢出在 C 里是有定义的回绕行为，JS 那边用 Math.imul 复现。
 * ------------------------------------------------------------------------ */
static unsigned int g_seed = 1u;

static void lcg_seed(unsigned int s)
{
    g_seed = s;
}

/* 返回 [0, 1) 的均匀随机数。取中间 15 位是因为 LCG 的低位周期很短、
 * 随机性差，这也是 C 标准库 rand() 的经典做法。 */
static float lcg_rand(void)
{
	// 1103515245u 12345u 这两个常数是 POSIX/C 标准库 rand() 的"法定"线性同余生成器（LCG）参数,
	// 历史上Unix 的 rand() 实现约定，后来被 POSIX/SUS 标准固化下来。
	// 基于经验挑选，无数学证明。它们的选择是为了让生成的随机数序列具有较好的统计特性和较长的周期。
	// 其它随机数算法：glibc 的减法生成器、Mersenne Twister、xoroshiro128+、PCG32 等。
    g_seed = g_seed * 1103515245u + 12345u;
    return (float)((g_seed >> 16) & 0x7FFFu) / 32768.0f;
}

/* ---------------------------------------------------------------------------
 * XOR 的全部 4 个样本。输入两位、输出一位——这就是整个「数据集」。
 * 和 semeion 那 1593 张手写数字比起来小得可怜，
 * 但训练循环的骨架一模一样。
 * ------------------------------------------------------------------------ */
static const float xor_in[4][2]  = {{0, 0}, {0, 1}, {1, 0}, {1, 1}};
static const float xor_out[4][1] = {  {0},    {1},    {1},    {0}};

/* ---------------------------------------------------------------------------
 * 用 LCG 重新初始化网络的权重与偏置，范围与 Tinn 内部一致：[-0.5, 0.5]。
 * xtbuild() 已经用 rand() 随机过一遍了，这里把它覆盖掉，只为可复现。
 * ------------------------------------------------------------------------ */
static void reseed_weights(const Tinn t, unsigned int seed)
{
    lcg_seed(seed);
    for(int i = 0; i < t.nw; i++) t.w[i] = lcg_rand() - 0.5f;
    for(int i = 0; i < t.nb; i++) t.b[i] = lcg_rand() - 0.5f;
}

/* ---------------------------------------------------------------------------
 * 把网络学到的那张「面」用 ASCII 打出来。
 * 横轴是 in[0]（左值），纵轴是 in[1]（右值），格子里的字符代表输出高低。
 * 训练成功时四个角应当是 [低 高 / 高 低] 的棋盘格。
 * ------------------------------------------------------------------------ */
static void print_surface(const Tinn t)
{
    static const char* shades = " .:-=+*#%@";   /* 由低到高 10 级 */
    const int n = 17;
    printf("\n    模型学到的曲面（纵轴 in[1] 由 1 到 0，横轴 in[0] 由 0 到 1）\n");
    for(int r = 0; r < n; r++)
    {
        const float y = 1.0f - (float) r / (n - 1);
        printf("    %4.2f |", (double) y);
        for(int c = 0; c < n; c++)
        {
            const float in[2] = { (float) c / (n - 1), y };
            const float z = xtpredict(t, in)[0];
            int k = (int)(z * 10.0f);
            if(k < 0) k = 0;
            if(k > 9) k = 9;
            printf("%c%c", shades[k], shades[k]);
        }
        printf("|\n");
    }
    printf("         +");
    for(int c = 0; c < n; c++) printf("--");
    printf("+\n");
    printf("          0.00%*s1.00      低 %s 高\n", 2 * n - 8, "", shades);
}

int main(int argc, char* argv[]){
    /* 超参数，全部可以用命令行覆盖。默认值对齐 GENANN 的 example1：
     *   隐藏层 4 个神经元、学习率 3、训练 3000 轮。
     * 学习率取到 3 这么大，是因为样本只有 4 条、网络只有几个权重，
     * 大步长能更快跨过 sigmoid 的平坦区；真实数据集上这么干必然震荡。
     * 隐藏层与轮数则比 GENANN 大一截，原因见文件顶部的差异说明。 */
    unsigned int seed = 3u;//种子
    int   nhid       = 4;//隐藏神经元数
    float rate       = 3.0f;//学习率
    int   iterations = 3000;//轮数

    for(int i = 1; i < argc; i++) {
        if(!strcmp(argv[i], "-s") && i + 1 < argc) seed       = (unsigned int) atoi(argv[++i]);
        else if(!strcmp(argv[i], "-n") && i + 1 < argc) nhid       = atoi(argv[++i]);
        else if(!strcmp(argv[i], "-r") && i + 1 < argc) rate       = (float) atof(argv[++i]);
        else if(!strcmp(argv[i], "-i") && i + 1 < argc) iterations = atoi(argv[++i]);
        else {
            printf("用法: %s [-s 种子] [-n 隐藏神经元数] [-r 学习率] [-i 轮数]\n", argv[0]);
            return 1;
        }
    }

    printf("Tinn XOR 示例（移植自 GENANN example1）\n");
    printf("结构 2 → %d → 1   学习率 %.3f   训练 %d 轮   种子 %u\n\n",
           nhid, (double) rate, iterations, seed);

    /* 建网：2 个输入、nhid 个隐藏神经元、1 个输出。
     * 2 个隐藏神经元是学会 XOR 的理论最小值——
     * 一个学 OR、一个学 AND，输出层再算「OR 且非 AND」。 */
    const Tinn tinn = xtbuild(2, nhid, 1);
    reseed_weights(tinn, seed);

    printf("初始权重: ");
    for(int i = 0; i < tinn.nw; i++) printf("%+.5f ", (double) tinn.w[i]);
    printf("\n初始偏置: %+.5f %+.5f\n\n", (double) tinn.b[0], (double) tinn.b[1]);

    /* 训练：把 4 个样本反复喂进去。每喂一条就立刻更新一次权重，
     * 这就是在线学习（随机梯度下降）。 */
    float first_err = 0.0f, err = 0.0f;
    for(int i = 0; i < iterations; i++)
    {
        err = 0.0f;
        for(int j = 0; j < 4; j++)
            err += xttrain(tinn, xor_in[j], xor_out[j], rate);
        if(i == 0)
            first_err = err;
        /* 误差应当单调下降。若它长时间卡在 0.5 附近不动，
         * 说明这次落进了局部极小值——换个种子重来即可。 */
        if(i % 50 == 0 || i == iterations - 1)
            printf("第 %4d 轮  总误差 %.8f\n", i, (double) err);
    }

    printf("\n最终权重: ");
    for(int i = 0; i < tinn.nw; i++) printf("%+.5f ", (double) tinn.w[i]);
    printf("\n最终偏置: %+.5f %+.5f\n", (double) tinn.b[0], (double) tinn.b[1]);

    /* 推理：xtpredict() 只做前向传播，返回指向内部输出缓冲的指针。
     * 网络的真实输出是 (0,1) 之间的小数，四舍五入后才是 0 / 1。 */
    printf("\n输入      期望   实际输出    判定\n");
    int ok = 0;
    for(int j = 0; j < 4; j++)
    {
        const float z = xtpredict(tinn, xor_in[j])[0];
        const int   r = z > 0.5f ? 1 : 0;
        const int   e = (int) xor_out[j][0];
        if(r == e) ok++;
        printf("[%.0f, %.0f]      %d    %.6f    %d  %s\n",
               (double) xor_in[j][0], (double) xor_in[j][1], e, (double) z, r,
               r == e ? "✓" : "✗");
    }

    print_surface(tinn);

    printf("\n误差 %.6f → %.6f（降到 1/%.1f）   4 个样本答对 %d 个：%s\n",
           (double) first_err, (double) err,
           err > 0 ? (double)(first_err / err) : 0.0, ok,
           ok == 4 ? "学会了 XOR" : "没学会，换个种子（-s）或加大隐藏层（-n）再试");

    xtfree(tinn);
    return ok == 4 ? 0 : 2;
}
