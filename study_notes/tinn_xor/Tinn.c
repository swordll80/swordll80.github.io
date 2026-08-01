/* ===========================================================================
 * Tinn 核心实现
 * ---------------------------------------------------------------------------
 * 阅读顺序建议：
 *   ① 几个数学小函数（err / pderr / act / pdact）—— 误差函数与激活函数及其导数
 *   ② fprop()  —— 前向传播，最容易读懂
 *   ③ bprop()  —— 反向传播，全库唯一需要动脑的地方
 *   ④ xtbuild() —— 建网与内存分配（注意 w 和 x 共用一块内存的技巧）
 *   ⑤ xtsave() / xtload() —— 存盘与读盘
 *
 * 【符号约定】设某神经元的加权和为 net，激活后输出为 y = act(net)，
 * 期望输出为 tg，误差函数 E = ½Σ(y - tg)²。反向传播的核心是链式法则：
 *
 *     ∂E/∂权重 = ∂E/∂y · ∂y/∂net · ∂net/∂权重
 *              = pderr(y,tg) · pdact(y) · 该权重对应的输入
 *
 * 下面代码里的变量 a 就是 ∂E/∂y，b 就是 ∂y/∂net。
 * ===========================================================================
 */

#include "Tinn.h"
/* 数据状态记录器。未调用 xt_trace_open() 时，下面所有 xt_trace_* 调用
 * 都是空操作，Tinn 的计算结果与原版逐位一致。详见 trace.h。 */
#include "trace.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

// Computes error.
// 单个输出的误差：E = ½(a - b)²。
// 前面那个 ½ 是为了让求导后的系数 2 被约掉，公式更干净（见下面的 pderr）。
static float err(const float a, const float b)
{
    return 0.5f * (a - b) * (a - b);
}

// Returns partial derivative of error function.
// 误差函数对输出 a 的偏导：∂E/∂a = a - b。
// 正是因为 err() 里带了 ½，这里才不会多出一个系数 2。
static float pderr(const float a, const float b)
{
    return a - b;
}

// Computes total error of target to output.
// 把所有输出神经元的误差加起来，作为衡量「这次预测有多差」的标量指标。
static float toterr(const float* const tg, const float* const o, const int size)
{
    float sum = 0.0f;
    for(int i = 0; i < size; i++)
        sum += err(tg[i], o[i]);
    return sum;
}

// Activation function.
// 激活函数：Logistic sigmoid，f(a) = 1/(1+e⁻ᵃ)，把任意实数压缩到 (0, 1)。
// Tinn 只提供这一种激活函数，输入层→隐藏层、隐藏层→输出层都用它。
static float act(const float a)
{
    return 1.0f / (1.0f + expf(-a));
}

// Returns partial derivative of activation function.
// sigmoid 的导数：f'(net) = f(net)·(1 - f(net)) = y·(1 - y)。
// 注意这里传入的参数 a 是「激活之后的输出 y」而不是加权和 net——
// 正因为 sigmoid 的导数可以只用输出值表示，才省去了保存 net 的开销。
static float pdact(const float a)
{
    return a * (1.0f - a);
}

// Returns floating point random from 0.0 - 1.0.
// [0, 1] 上的均匀随机数。注意 Tinn 不负责调用 srand()，需要使用者自己播种，
// 否则每次运行的初始权重完全相同（rand 默认种子是 1）。
static float frand()
{
    return rand() / (float) RAND_MAX;
}

// Performs back propagation.
/* 反向传播：按梯度下降更新所有权重。必须先调用 fprop()，因为这里要用到
 * 前向传播留下的 t.h（隐藏层输出）和 t.o（输出层输出）。
 *
 * 外层按隐藏神经元 i 遍历，一趟同时干了两件事：
 *   1. 更新「隐藏层 → 输出层」的权重 x；
 *   2. 顺便把该隐藏神经元收到的误差回传量累加到 sum 里，
 *      再用它更新「输入层 → 隐藏层」的权重 w。
 * 这种写法把两层的更新揉进一个循环，是 Tinn 能压到 200 行的原因之一。
 *
 * 【注意】本函数不更新偏置 b[0] / b[1]，它们始终保持随机初值。
 * 这是 Tinn 为极简做出的取舍，属于已知的实现特点而非笔误。 */
static void bprop(const Tinn t, const float* const in, const float* const tg, float rate)
{
    /* 【追踪埋点】δ_j 与 δ_i 是反向传播的核心中间量，原版算完立刻就被用掉、
     * 不留痕迹。这里在开启细粒度记录时把它们抄一份出来；未开启时下面两个
     * 指针为 NULL，只多两次判空，不影响原有计算。 */
    float* const dout = xt_trace_scratch(2, t.nops);   // 输出层误差项 δ_j
    float* const dhid = xt_trace_scratch(3, t.nhid);   // 隐藏层误差项 δ_i
    // 更新前先把全部权重快照一份，事后即可算出本步的权重增量 Δw。
    xt_trace_bprop_snapshot(t);
    for(int i = 0; i < t.nhid; i++)
    {
        float sum = 0.0f;
        // Calculate total error change with respect to output.
        for(int j = 0; j < t.nops; j++)
        {
            const float a = pderr(t.o[j], tg[j]);  // ∂E/∂o_j = o_j - tg_j
            const float b = pdact(t.o[j]);         // ∂o_j/∂net_j = o_j(1-o_j)
            // a*b 就是输出神经元 j 的误差项 δ_j = ∂E/∂net_j。
            // 把 δ_j 乘上连接权重后累加，得到隐藏神经元 i 分摊到的误差。
            // 这一步必须用「更新前」的权重，所以放在下面那行赋值之前。
            if(dout) dout[j] = a * b;
            sum += a * b * t.x[j * t.nhid + i];
            // Correct weights in hidden to output layer.
            // 梯度下降：x_ji -= 学习率 × δ_j × 该权重对应的输入(即 h_i)。
            // 权重按「输出神经元 j 为一组」排列，故下标为 j*nhid + i。
            t.x[j * t.nhid + i] -= rate * a * b * t.h[i];
        }
        // Correct weights in input to hidden layer.
        // 隐藏神经元 i 的误差项 δ_i = sum × pdact(h_i)，
        // 再乘上该权重对应的输入 in[j] 即为梯度。
        // 权重按「隐藏神经元 i 为一组」排列，故下标为 i*nips + j。
        if(dhid) dhid[i] = sum * pdact(t.h[i]);
        for(int j = 0; j < t.nips; j++)
            t.w[i * t.nips + j] -= rate * sum * pdact(t.h[i]) * in[j];
    }
    // 【追踪埋点】落盘一条 BPROP 状态：δ、权重增量与更新后的权重。
    xt_trace_bprop_result(t, in, tg, dout, dhid, rate);
}

// Performs forward propagation.
/* 前向传播：把输入逐层算到输出，结果留在 t.h 和 t.o 里。 */
static void fprop(const Tinn t, const float* const in)
{
    /* 【追踪埋点】激活前的加权和 net 原版是个循环内的局部变量，算完就没了。
     * 开启细粒度记录时借用临时槽位把它留下来，好在演示里展示
     * 「加权求和 → 挤进 (0,1)」这两步的区别；未开启时指针为 NULL。 */
    float* const hsum = xt_trace_scratch(0, t.nhid);
    float* const osum = xt_trace_scratch(1, t.nops);
    // Calculate hidden layer neuron values.
    // 隐藏层：每个神经元把所有输入加权求和，加上共用偏置 b[0]，再过 sigmoid。
    for(int i = 0; i < t.nhid; i++)
    {
        float sum = 0.0f;
        for(int j = 0; j < t.nips; j++)
            sum += in[j] * t.w[i * t.nips + j];
        if(hsum) hsum[i] = sum + t.b[0];
        t.h[i] = act(sum + t.b[0]);
    }
    xt_trace_fprop_hidden(t, in, hsum);
    // Calculate output layer neuron values.
    // 输出层：以隐藏层的输出为输入，加上共用偏置 b[1]，再过 sigmoid。
    // 因此输出恒在 (0, 1) 之间——Tinn 天然适合分类，做回归则需自行缩放目标值。
    for(int i = 0; i < t.nops; i++)
    {
        float sum = 0.0f;
        for(int j = 0; j < t.nhid; j++)
            sum += t.h[j] * t.x[i * t.nhid + j];
        if(osum) osum[i] = sum + t.b[1];
        t.o[i] = act(sum + t.b[1]);
    }
    xt_trace_fprop_output(t, osum);
}

// Randomizes tinn weights and biases.
/* 把所有权重和偏置随机初始化到 [-0.5, 0.5]。
 * 必须随机而不能全部置零：若同层神经元初值完全相同，它们收到的梯度也完全相同，
 * 会永远保持一致（对称性无法打破），整个隐藏层等价于只有一个神经元。 */
static void wbrand(const Tinn t)
{
    for(int i = 0; i < t.nw; i++) t.w[i] = frand() - 0.5f;
    for(int i = 0; i < t.nb; i++) t.b[i] = frand() - 0.5f;
}

// Returns an output prediction given an input.
/* 推理：只做前向传播，返回指向内部输出缓冲 t.o 的指针（长度 nops）。 */
float* xtpredict(const Tinn t, const float* const in)
{
    fprop(t, in);
    return t.o;
}

// Trains a tinn with an input and target output with a learning rate. Returns target to output error.
/* 训练一步 = 前向传播 + 反向传播。
 * 返回的误差是用「更新前」的权重算出来的（bprop 不会改动 t.o），
 * 所以它反映的是这一步训练之前的表现。 */
float xttrain(const Tinn t, const float* const in, const float* const tg, float rate)
{
    fprop(t, in);
    // 【追踪埋点】在「已经算出预测、但还没开始改权重」这个时刻记一笔误差，
    // 它正是反向传播的出发点。
    xt_trace_error(t, tg);
    bprop(t, in, tg, rate);
    return toterr(tg, t.o, t.nops);
}

// Constructs a tinn with number of inputs, number of hidden neurons, and number of outputs
/* 建网。注意这里的内存技巧：w 一次性分配了两层的全部权重，
 * x 只是指向这块内存中间的一个偏移，并非独立分配——所以 xtfree 只 free(w)。 */
Tinn xtbuild(const int nips, const int nhid, const int nops)
{
    Tinn t;
    // Tinn only supports one hidden layer so there are two biases.
    // 只有一个隐藏层，所以偏置固定两个：隐藏层一个、输出层一个。
    t.nb = 2;
    // 权重总数 = 输入层→隐藏层(nhid*nips) + 隐藏层→输出层(nhid*nops)。
    t.nw = nhid * (nips + nops);
    // calloc 会把内存清零；紧接着 wbrand() 会用随机值覆盖它们。
    t.w = (float*) calloc(t.nw, sizeof(*t.w));
    // x 指向 w 中「隐藏层→输出层」那一段的起点，与 w 共享同一块内存。
    t.x = t.w + nhid * nips;
    t.b = (float*) calloc(t.nb, sizeof(*t.b));
    t.h = (float*) calloc(nhid, sizeof(*t.h));
    t.o = (float*) calloc(nops, sizeof(*t.o));
    t.nips = nips;
    t.nhid = nhid;
    t.nops = nops;
    wbrand(t);
    return t;
}

// Saves a tinn to disk.
/* 存盘。文本格式，每行一个数：
 *     第 1 行：nips nhid nops
 *     随后 nb 行：偏置
 *     随后 nw 行：权重
 * 【注意】用的是 %f，只保留 6 位小数，存盘会损失一点精度。
 * 对推理精度影响通常可以忽略，但存盘再读回的网络不会与原网络逐位相同。
 * 另外这里没有检查 fopen 是否成功，路径不可写时会崩溃。 */
void xtsave(const Tinn t, const char* const path)
{
    FILE* const file = fopen(path, "w");
    // Save header.
    fprintf(file, "%d %d %d\n", t.nips, t.nhid, t.nops);
    // Save biases and weights.
    for(int i = 0; i < t.nb; i++) fprintf(file, "%f\n", (double) t.b[i]);
    for(int i = 0; i < t.nw; i++) fprintf(file, "%f\n", (double) t.w[i]);
    fclose(file);
}

// Loads a tinn from disk.
/* 读盘。先读出三个规模参数，用它们 xtbuild 出一个新网络（此时权重是随机的），
 * 再逐个读入偏置与权重把随机值覆盖掉。
 * 同样没有检查 fopen 与 fscanf 的返回值，文件缺失或损坏时行为未定义。 */
Tinn xtload(const char* const path)
{
    FILE* const file = fopen(path, "r");
    int nips = 0;
    int nhid = 0;
    int nops = 0;
    // Load header.
    fscanf(file, "%d %d %d\n", &nips, &nhid, &nops);
    // Build a new tinn.
    const Tinn t = xtbuild(nips, nhid, nops);
    // Load bias and weights.
    for(int i = 0; i < t.nb; i++) fscanf(file, "%f\n", &t.b[i]);
    for(int i = 0; i < t.nw; i++) fscanf(file, "%f\n", &t.w[i]);
    fclose(file);
    return t;
}

// Frees object from heap.
/* 释放堆内存。注意只 free 了 w、b、h、o 四个指针——
 * x 指向 w 内部，不能也不需要单独释放，否则会造成重复释放崩溃。 */
void xtfree(const Tinn t)
{
    free(t.w);
    free(t.b);
    free(t.h);
    free(t.o);
}

// Prints an array of floats. Useful for printing predictions.
/* 打印浮点数组，调试查看预测结果时很方便。
 * 转成 double 是因为可变参数函数会把 float 自动提升为 double，
 * 显式转换可以避免编译器发出相关告警。 */
void xtprint(const float* arr, const int size)
{
    for(int i = 0; i < size; i++)
        printf("%f ", (double) arr[i]);
    printf("\n");
}
