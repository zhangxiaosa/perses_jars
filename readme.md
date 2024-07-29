# Reduce Framework

Our reduce framework is designed to minimize programs by invoking multiple reducers. It is highly versatile and can work with various types of programs and reducers to help you find the smallest version of your program that still exhibits the desired properties.

## Usage

To use the reduce framework, follow these steps:

1. **Place your program and `oracle.sh` script in the same directory**:
   - The `oracle.sh` script should return 0 when the program exhibits the desired behavior.

2. **Template for `oracle.sh`**:
   Here is a template for the `oracle.sh` script:

   ```bash
   #!/bin/bash

   # Compile the program
   gcc -o program program.c

   # Run the program and check the result
   ./program > output.txt
   grep -q "desired output" output.txt

   # Return 0 if the output is as expected, otherwise return 1
   if [ $? -eq 0 ]; then
     exit 0
   else
     exit 1
   fi
   ```

3. **Running the Reducer**:
   - Ensure that the `program` and `oracle.sh` script are executable.
   - The framework will create a temporary folder, execute `oracle.sh` inside it, and check if it returns 0.

## Flags

Our reduce framework supports several flags to control its behavior:

- `-xxx`: Description of what this flag does. For example, this flag might control the verbosity of the output.
- `-yyy`: Description of what this flag does. For example, this flag might specify a different directory for temporary files.

### Example Command with Flags

```bash
./reduce.sh -xxx -yyy
```

### Explanation of Flags

- **-xxx**: Use this flag to enable detailed logging. This can be useful for debugging purposes or for understanding the reduction process in more detail.
  
  ```bash
  ./reduce.sh -xxx
  ```

- **-yyy**: Use this flag to specify a custom directory for temporary files. This is useful if you want to control where intermediate files are stored during the reduction process.
  
  ```bash
  ./reduce.sh -yyy /custom/temp/dir
  ```

## Ensuring `oracle.sh` Works in a Temporary Directory

It's essential to ensure that `oracle.sh` can run in an arbitrary temporary directory containing only the files being reduced. Follow these steps to verify:

1. **Prepare your directory structure**:
   ```
   my_reduce_project/
   ├── program.c
   └── oracle.sh
   ```

2. **Ensure `oracle.sh` is executable**:
   ```bash
   chmod +x oracle.sh
   ```

3. **Test `oracle.sh` in a temporary directory**:
   ```bash
   DIR=$(mktemp -d)
   cp /path/to/your/program.c $DIR
   cp /path/to/your/oracle.sh $DIR
   cd $DIR
   ./oracle.sh
   echo $?
   ```

   The command above should result in "0" being echoed to the terminal. If it does not, you need to ensure that `oracle.sh` correctly handles being run in a temporary directory.

## Example Workflow

1. **Run the reduce framework with your program and oracle**:
   ```bash
   ./reduce.sh
   ```

2. **Run with flags for additional control**:
   ```bash
   ./reduce.sh -xxx -yyy /custom/temp/dir
   ```

## Notes

- The `oracle.sh` script is critical as it determines if the reduced program is still valid. Make sure it returns 0 for valid programs.
- The temporary directory used for running the oracle will be cleaned up automatically after each test.

By following these steps, using the provided template, and leveraging the available flags, you can effectively use the reduce framework to minimize your programs.