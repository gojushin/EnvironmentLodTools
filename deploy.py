import os
import zipfile


def increment_version_in_file(filepath):
    """
    Increments the version number in the specified file by 1.

    :param filepath: The path to the file where the version number is located.
    :type filepath: str

    :raises FileNotFoundError: If the specified file does not exist.

    This function opens the file specified by `filepath` and reads its contents. It then searches for the line that
    contains the string 'bl_info'. If found, it searches for the line that contains the string '"version":'. If found,
    it extracts the version number from the line and increments it by 1. The modified line is then replaced in the
    list of lines. If any changes were made, the function writes the modified lines back to the file.

    Note:
        The function assumes that the version number is represented as a tuple of three integers enclosed in parentheses.
        It also assumes that the version number is the only occurrence of the string '"version":' in the file.
    """
    with open(filepath, 'r') as file:
        lines = file.readlines()

    changed = False
    for i, line in enumerate(lines):
        if 'bl_info' in line:
            start = line.find('bl_info')
            if start != -1:
                for j in range(i, len(lines)):
                    if '"version":' in lines[j]:
                        version_index = lines[j].find('"version":')
                        tuple_start = lines[j].find('(', version_index)
                        tuple_end = lines[j].find(')', version_index)
                        if tuple_start != -1 and tuple_end != -1:
                            version_str = lines[j][tuple_start+1:tuple_end]
                            version_numbers = version_str.split(',')
                            if len(version_numbers) == 3:
                                new_version = (int(version_numbers[0]), int(version_numbers[1]), int(version_numbers[2]) + 1)
                                new_version_str = f'({new_version[0]}, {new_version[1]}, {new_version[2]})'
                                lines[j] = lines[j][:tuple_start+1] + new_version_str[1:-1] + lines[j][tuple_end:]
                                changed = True
                                break
            if changed:
                break

    if changed:
        with open(filepath, 'w') as file:
            file.writelines(lines)


def process_directory(directory):
    """
    Loops through all files in a directory, incrementing the version number in each Python file.
    :param directory: The directory to process.
    :type directory: str
    """
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                increment_version_in_file(os.path.join(root, file))


def zip_directory(directory):
    """
    Zips all files in a directory.
    :param directory: The directory to zip.
    :type directory: str
    """
    zip_filename = f"{directory}.zip"
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, start=os.path.join(directory, '..')))


if __name__ == "__main__":
    user_defined_folder = input("Enter the folder name within the current directory: ")
    if not user_defined_folder:
        user_defined_folder = [d for d in os.listdir() if os.path.isdir(d)][0]  # Get the first dir  in the current dir
    if os.path.isdir(user_defined_folder):
        process_directory(user_defined_folder)
        zip_directory(user_defined_folder)
        print(f"Processed and zipped the directory {user_defined_folder} successfully.")
    else:
        print("The specified directory does not exist.")
