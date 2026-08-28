# Container profile

`gradle:9.5.0-jdk17`をBaseに、JVM、Semantics、Coroutine、Flow、Interop、Compiler/Runtime、Engineering Labをimage build時に実行します。完成imageは`--network=none`で同じTaskをoffline再実行します。

```bash
scripts/container-verify.sh
```

Apple Native、JS、WasmはHost固有Toolchainを必要とするためLocal profileで検証し、Container profileはJVM必須GateのHost cache独立性を担当します。
