#!/usr/bin/env bash
set -euo pipefail

die() {
  printf '%s\n' "$1" >&2
  return 1
}

main() {
  local system="${SYSTEM:-x86_64-linux}"
  local packages_json="${PACKAGES:-[]}"
  local exclude_json="${EXCLUDE:-[]}"
  local image_package="${IMAGE_PACKAGE:-}"
  local image_artifact="${IMAGE_ARTIFACT:-}"
  local archive_file="${IMAGE_ARCHIVE_FILE:-image.tar.gz}"
  local output_dir="${OUTPUT_DIR:-${RUNNER_TEMP:-${TMPDIR:-/tmp}}}"
  local available_file actual_system attr input supported image_path

  if [[ ! "$system" =~ ^[A-Za-z0-9_-]+$ ]]
  then
    die 'Invalid Nix system name.'
    return 1
  fi
  if ! jq -e 'type == "array" and all(.[]; type == "string") and (length == (unique | length))' \
    <<< "$packages_json" >/dev/null
  then
    die 'packages must be a JSON array of unique strings.'
    return 1
  fi
  if ! jq -e 'type == "array" and all(.[]; type == "string") and (length == (unique | length))' \
    <<< "$exclude_json" >/dev/null
  then
    die 'exclude must be a JSON array of unique strings.'
    return 1
  fi

  if [[ -n "$image_package$image_artifact" || "$archive_file" != image.tar.gz ]]
  then
    if [[ -z "$image_package" || -z "$image_artifact" || -z "$archive_file" ]]
    then
      die 'Image package, artifact name and archive filename must be provided together.'
      return 1
    fi
  fi
  if [[ -n "$image_package" ]]
  then
    if [[ ! "$image_package" =~ ^[A-Za-z0-9][A-Za-z0-9_+-]*$ ]]
    then
      die 'Invalid image package name.'
      return 1
    fi
    if [[ ! "$image_artifact" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]]
    then
      die 'Invalid image artifact name.'
      return 1
    fi
    if [[ ! "$archive_file" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]]
    then
      die 'Invalid image archive filename.'
      return 1
    fi
  fi

  mkdir -p "$output_dir/outs" || {
    die 'Could not create the Nix output directory.'
    return 1
  }
  actual_system="$(nix eval --impure --raw --expr builtins.currentSystem)" || {
    die 'Could not determine the runner Nix system.'
    return 1
  }
  if [[ "$actual_system" != "$system" ]]
  then
    die 'Requested Nix system does not match this runner.'
    return 1
  fi

  available_file="$output_dir/nix-packages"
  nix eval --json ".#packages.$system" --apply builtins.attrNames > "$available_file" || {
    die 'Could not list native flake packages.'
    return 1
  }
  if ! jq -e 'type == "array" and all(.[]; type == "string")' "$available_file" >/dev/null
  then
    die 'Flake package attributes were not a JSON string array.'
    return 1
  fi

  while IFS= read -r attr
  do
    if [[ ! "$attr" =~ ^[A-Za-z0-9][A-Za-z0-9_+-]*$ ]]
    then
      die 'Invalid explicit package attribute name.'
      return 1
    fi
    if ! jq -e --arg attr "$attr" 'index($attr) != null' "$available_file" >/dev/null
    then
      die 'Requested package attribute does not exist.'
      return 1
    fi
  done < <(jq -r '.[]' <<< "$packages_json")

  while IFS= read -r attr
  do
    if [[ ! "$attr" =~ ^[A-Za-z0-9][A-Za-z0-9_+-]*$ ]]
    then
      die 'Invalid excluded package attribute name.'
      return 1
    fi
  done < <(jq -r '.[]' <<< "$exclude_json")

  if [[ "$(jq 'length' <<< "$packages_json")" == 0 ]]
  then
    jq -c --argjson exclude "$exclude_json" \
      '[.[] | select(. as $n | $exclude | index($n) | not)]' \
      "$available_file" > "$output_dir/nix-selected-packages" || {
      die 'Could not select native flake packages.'
      return 1
    }
  else
    jq -c --argjson exclude "$exclude_json" \
      '[.[] | select(. as $n | $exclude | index($n) | not)]' \
      <<< "$packages_json" > "$output_dir/nix-selected-packages" || {
      die 'Could not select native flake packages.'
      return 1
    }
  fi

  if [[ "$(jq 'length' "$output_dir/nix-selected-packages")" -eq 0 ]]
  then
    die 'Package selection is empty.'
    return 1
  fi

  while IFS= read -r attr
  do
    if [[ ! "$attr" =~ ^[A-Za-z0-9][A-Za-z0-9_+-]*$ ]]
    then
      die 'Invalid selected package attribute name.'
      return 1
    fi
  done < <(jq -r '.[]' "$output_dir/nix-selected-packages")

  if [[ -n "$image_package" ]]
  then
    if ! jq -e --arg image "$image_package" 'index($image) != null' \
      "$output_dir/nix-selected-packages" >/dev/null
    then
      die 'The image package must be included in the selected package set.'
      return 1
    fi
  fi

  : > "$output_dir/nix-paths" || {
    die 'Could not initialize the Niks3 path list.'
    return 1
  }
  declare -A seen_paths=()

  build_one() {
    local suffix="$1"
    local installable="$2"
    local output_file="$output_dir/outs/$suffix"
    local index=0
    local path

    nix build --no-link --print-build-logs --print-out-paths "$installable" > "$output_file" || {
      die 'A selected Nix package or dependency build failed.'
      return 1
    }
    while IFS= read -r path
    do
      [[ -n "$path" ]] || continue
      if [[ "$path" != /nix/store/* ]]
      then
        die 'Nix returned an invalid store path.'
        return 1
      fi
      if [[ -z "${seen_paths[$path]+present}" ]]
      then
        seen_paths["$path"]=1
        printf '%s-%s %s\n' "$suffix" "$index" "$path" >> "$output_dir/nix-paths" || {
          die 'Could not record a Niks3 store path.'
          return 1
        }
      fi
      index=$((index + 1))
    done < "$output_file"

    if [[ "$index" -eq 0 ]]
    then
      die 'Nix returned no output paths for a package.'
      return 1
    fi
  }

  while IFS= read -r attr
  do
    [[ -n "$attr" ]] || continue
    build_one "$attr" ".#packages.$system.$attr" || return 1
    for input in cargoArtifacts cargoVendorDir
    do
      supported="$(nix eval --json ".#packages.$system.$attr" \
        --apply "p: p ? $input && builtins.isAttrs p.$input && p.$input ? outPath")" || {
        die 'Could not inspect package dependency outputs.'
        return 1
      }
      if [[ "$supported" != true ]]
      then
        continue
      fi
      build_one "$attr-$input" ".#packages.$system.$attr.$input" || return 1
    done
  done < <(jq -r '.[]' "$output_dir/nix-selected-packages")

  if [[ -n "$image_package" ]]
  then
    if [[ ! -f "$output_dir/outs/$image_package" ]]
    then
      die 'The configured image package was not built.'
      return 1
    fi
    local -a image_outputs=()
    mapfile -t image_outputs < "$output_dir/outs/$image_package" || {
      die 'Could not read image package output paths.'
      return 1
    }
    if [[ "${#image_outputs[@]}" -ne 1 ]]
    then
      die 'The image package must produce exactly one output path.'
      return 1
    fi
    image_path="${image_outputs[0]}"
    if [[ ! -f "$image_path" ]]
    then
      die 'The image package output is not a regular archive file.'
      return 1
    fi
    cp --dereference "$image_path" "$output_dir/$archive_file" || {
      die 'Could not export the image archive.'
      return 1
    }
  fi
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]
then
  main "$@"
fi

# vim: set ft=sh et ts=2 sw=2 :
