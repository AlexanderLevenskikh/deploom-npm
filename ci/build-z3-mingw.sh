#!/usr/bin/env bash
# Build the pinned Python binding's own Z3 release with the MinGW-w64 runtime.
set -euo pipefail
archive=z3-solver-4.13.0.0.tar.gz
url=https://files.pythonhosted.org/packages/3a/fd/e3f5850fd04480a942aca9f9f7520d3fa5b57731335c221a11f55bb6d91a/$archive
sha=52588e92aec7cb338fd6288ce93758ae01770f62ca0c80e8f4f2b2333feaf51b
mkdir -p build/solver/output
cd build/solver
curl --fail --location --retry 3 "$url" -o "$archive"
echo "$sha  $archive" | sha256sum --check --strict
tar xzf "$archive"
linkflags='-static -static-libgcc -static-libstdc++ -Wl,--no-insert-timestamp'
cmake -S z3-solver-4.13.0.0/core -B obj -G Ninja \
  -DCMAKE_SYSTEM_NAME=Windows -DCMAKE_SYSTEM_PROCESSOR=AMD64 \
  -DCMAKE_C_COMPILER=x86_64-w64-mingw32-gcc-posix -DCMAKE_CXX_COMPILER=x86_64-w64-mingw32-g++-posix \
  -DCMAKE_RC_COMPILER=x86_64-w64-mingw32-windres -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_FLAGS_RELEASE='-O2 -DNDEBUG' \
  "-DCMAKE_SHARED_LINKER_FLAGS=$linkflags" "-DCMAKE_EXE_LINKER_FLAGS=$linkflags" \
  -DZ3_INCLUDE_GIT_HASH=OFF -DZ3_INCLUDE_GIT_DESCRIBE=OFF -DZ3_BUILD_LIBZ3_SHARED=ON
cmake --build obj --parallel "$(nproc)" --target libz3 shell
for pair in 'libz3.dll:libz3.dll' 'z3.exe:z3.exe'; do
  pattern=${pair%%:*}
  if [[ "$pattern" == libz3.dll ]]; then pattern='*z3.dll'; fi
  mapfile -t found < <(find obj -type f -iname "$pattern")
  [[ ${#found[@]} == 1 ]]
  x86_64-w64-mingw32-strip -o "output/${pair#*:}" "${found[0]}"
  imports=$(x86_64-w64-mingw32-objdump -p "output/${pair#*:}" | awk '/DLL Name:/ {print tolower($NF)}' | sort -u)
  echo "${pair#*:} imports:"
  echo "$imports"
  if grep -Eiq '^(vcruntime|msvcp[0-9]|mfc[0-9]|vcomp[0-9]|libstdc\+\+|libgcc|libwinpthread)' <<< "$imports"; then
    echo 'Unexpected external compiler runtime' >&2
    exit 1
  fi
done
cp z3-solver-4.13.0.0/core/LICENSE.txt output/Z3-LICENSE.txt
cp /usr/share/doc/mingw-w64-common/copyright output/MinGW-COPYRIGHT.txt
cp /usr/share/common-licenses/GPL-3 output/GCC-GPL-3.txt
cp /usr/share/doc/gcc-mingw-w64-base/copyright output/compiler-copyright.txt
test -f /usr/share/common-licenses/GPL-3
(cd output && sha256sum *.dll *.exe > SHA256SUMS)
