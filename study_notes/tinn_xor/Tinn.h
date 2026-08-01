/* ===========================================================================
 * Tinn (Tiny Neural Network) —— 200 行、零依赖的 C99 神经网络库
 * ---------------------------------------------------------------------------
 * 【这个库是什么】
 *   一个刻意做到极简的多层感知机实现：固定「输入层 → 一个隐藏层 → 输出层」
 *   三层结构，sigmoid 激活，标准反向传播训练，只依赖 C 标准库。
 *   整个实现不到 200 行，非常适合阅读学习，也适合塞进单片机等嵌入式环境。
 *
 * 【网络结构】固定为一个隐藏层，不可配置：
 *
 *      输入层 in            隐藏层 h            输出层 o
 *      (nips 个)            (nhid 个)           (nops 个)
 *         o ──────┐            o ──────┐           o
 *         o ──────┼─→ [w] ──→  o ──────┼─→ [x] ──→ o
 *         o ──────┘            o ──────┘           o
 *                 偏置 b[0] ────┘        偏置 b[1] ─┘
 *
 *   注意偏置的处理方式很特别：整个隐藏层共用一个偏置 b[0]，
 *   整个输出层共用一个偏置 b[1]，而不是每个神经元各有一个。
 *   这是 Tinn 为了极简做出的取舍，会略微限制模型的表达能力。
 *
 * 【命名约定】
 *   对外暴露的函数一律以 xt 开头（externed tinn 的缩写），充当命名空间。
 *
 * 【API 一览】
 *   xtbuild   建网      xtpredict 推理    xttrain 训练一步
 *   xtsave    存盘      xtload    读盘    xtfree  释放
 *   xtprint   打印浮点数组（调试用）
 *
 * 【注意事项】
 *   - Tinn 不会自己初始化随机数种子，请自行调用 srand()。
 *   - Tinn 结构体是按值传递的（只有 5 个指针和 5 个 int，拷贝很廉价），
 *     但内部指针指向堆内存，多个副本共享同一份权重，只能 xtfree 一次。
 * ===========================================================================
 */

#pragma once

typedef struct
{
    // All the weights.
    // 全部权重的起始指针，长度为 nw = nhid * (nips + nops)。
    // 前 nhid*nips 个是「输入层 → 隐藏层」的权重，紧接着的
    // nhid*nops 个是「隐藏层 → 输出层」的权重（由下面的 x 指向）。
    // 两段权重共用同一块 calloc 内存，因此只需 free(w) 一次。
    float* w;
    // Hidden to output layer weights.
    // 指向 w 内部的偏移位置（w + nhid*nips），即隐藏层到输出层的权重。
    // 它不是独立分配的内存，千万不要对 x 调用 free！
    float* x;
    // Biases.
    // 偏置，长度固定为 2：b[0] 给整个隐藏层用，b[1] 给整个输出层用。
    float* b;
    // Hidden layer.
    // 隐藏层各神经元激活后的输出，长度 nhid。它是前向传播的中间结果，
    // 反向传播时还要用到，所以必须保存下来。
    float* h;
    // Output layer.
    // 输出层各神经元的输出，长度 nops。xtpredict() 返回的就是这个指针。
    float* o;
    // Number of biases - always two - Tinn only supports a single hidden layer.
    // 偏置个数，恒为 2（因为 Tinn 只支持一个隐藏层）。
    int nb;
    // Number of weights.
    // 权重总数 = nhid * (nips + nops)。
    int nw;
    // Number of inputs.
    // 输入个数。
    int nips;
    // Number of hidden neurons.
    // 隐藏层神经元个数。这是唯一需要你调参的网络结构参数：
    // 太少则欠拟合（学不动），太多则过拟合且变慢。
    int nhid;
    // Number of outputs.
    // 输出个数。做 N 分类时通常取 N，配合独热编码使用。
    int nops;
}
Tinn;

/* 前向传播：给定输入，返回指向输出数组（长度 nops）的指针。
 * 返回的指针指向网络内部的 t.o 缓冲区，下次调用会被覆盖，
 * 需要保留结果请自行拷贝。 */
float* xtpredict(Tinn, const float* in);

/* 训练一步：先前向传播，再反向传播更新权重，返回本次的总误差。
 *   in   —— 输入，长度 nips
 *   tg   —— 期望输出（target），长度 nops
 *   rate —— 学习率
 * 返回值是训练「之前」那次前向传播结果与期望值的误差 ½Σ(tg-o)²，
 * 可用来观察训练是否在收敛。 */
float xttrain(Tinn, const float* in, const float* tg, float rate);

/* 建网：指定输入个数、隐藏层神经元个数、输出个数。
 * 权重与偏置会被随机初始化到 [-0.5, 0.5]。
 * 注意 Tinn 不检查 calloc 是否失败，也不校验参数合法性。 */
Tinn xtbuild(int nips, int nhid, int nops);

/* 把网络以纯文本格式保存到磁盘。 */
void xtsave(Tinn, const char* path);

/* 从磁盘读回网络（内部会先 xtbuild 再覆盖权重）。 */
Tinn xtload(const char* path);

/* 释放网络占用的堆内存。 */
void xtfree(Tinn);

/* 打印一个浮点数组，方便查看预测结果。 */
void xtprint(const float* arr, const int size);
