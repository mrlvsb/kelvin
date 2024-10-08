type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/**
 * Get data from API
 * @param url url to fetch
 * @param data data which will be sent to the API
 * @param method HTTP method, if you want to override the default GET/POST
 * @note If data is passed, the request will be a POST request, otherwise a GET request, if not overridden by method parameter
 * @returns $ReturnType, if the request was successful, otherwise undefined
 */
export const getFromAPI = async <$ReturnType>(
    url: string,
    data?: unknown,
    method?: Method
): Promise<$ReturnType | undefined> => {
    try {
        const response = await fetch(url, {
            method: method || (data ? 'POST' : 'GET'),
            body: data ? JSON.stringify(data) : undefined
        });

        if (!response.ok) {
            return undefined;
        }

        const json = await response.json();
        return json as $ReturnType;
    } catch (error) {
        console.error(error);
        return undefined;
    }
};

/**
 * Generate array with range of numbers from start
 * @param size size of the array
 * @param start starting number
 * @returns array of numbers from start to start + size
 */
export const generateRange = (size: number, start = 0) => {
    return Array.from({ length: size }).map((_, i) => i + start);
};
