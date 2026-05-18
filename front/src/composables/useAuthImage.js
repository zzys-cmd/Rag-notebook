import { useUserStore } from '../store/user';

export function useAuthImage() {
  const userStore = useUserStore();

  const getAllImages = async (md5) => {
    const token = userStore.token;
    if (!token) return {};

    try {
      const response = await fetch(`/knowledge/images/all/${md5}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) return {};
      const result = await response.json();
      if (result.code !== 200 || !result.data?.images) return {};
      return result.data.images;
    } catch {
      return {};
    }
  };

  const resolveImageUrls = (imagePaths, imageMap) => {
    return imagePaths
      .map(p => {
        const basename = p.split('/').pop().replace(/\.[^.]+$/, '');
        const key = Object.keys(imageMap).find(
          k => k.replace(/\.[^.]+$/, '') === basename
        );
        return key ? imageMap[key] : null;
      })
      .filter(Boolean);
  };

  return { getAllImages, resolveImageUrls };
}
